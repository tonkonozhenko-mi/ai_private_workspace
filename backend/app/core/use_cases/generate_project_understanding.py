import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.project_understanding import (
    ProjectRisk,
    ProjectRunCommand,
    ProjectStartPoint,
    ProjectUnderstanding,
)
from app.core.domain.rag_prompt import build_project_understanding_prompt
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.llm_provider import LLMProviderPort
from app.core.ports.llm_provider_factory import (
    LLMProviderFactoryError,
    LLMProviderFactoryPort,
)
from app.core.ports.project_understanding_repository import (
    ProjectUnderstandingRepositoryPort,
)
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


# Retrieval queries shape WHICH evidence the model sees, so we tune them per role.
# A tester pulls in test/verification context; a DevOps engineer pulls deploy/infra
# context; etc. This makes the analysis genuinely "through the role's eyes" rather
# than a generic summary with a one-line instruction. Each query is embedded and
# searched separately; chunks are deduped by source path and budgeted.
BASE_RETRIEVAL_QUERIES = [
    "architecture and what this project does",
    "risks, TODOs, missing pieces",
]
ROLE_RETRIEVAL_QUERIES: dict[str, list[str]] = {
    "developer": [
        "main modules and where to start reading the code",
        "tests",
        "configuration and environment",
    ],
    "devops": [
        "deployment and infrastructure",
        "CI/CD pipelines and release process",
        "configuration, environment variables, and secrets",
        "operational risks and failure modes",
    ],
    "tester": [
        "tests and test coverage",
        "how to run the tests",
        "critical paths and behavior that need verification",
        "untested, fragile, or error-prone areas",
    ],
    "business_analyst": [
        "what this project does and its main features",
        "who the users are and the main workflows",
        "limitations, gaps, and assumptions",
    ],
    "documentation": [
        "how the project is structured and how to onboard",
        "public interfaces and APIs",
        "where documentation is thin or missing",
    ],
    "support_incident": [
        "operational behavior, runbooks, and diagnostics",
        "failure modes, logging, and error handling",
        "configuration and environment",
    ],
    "manager_summary": [
        "overall readiness, status, and release process",
        "tests and quality",
        "deployment and infrastructure",
    ],
}


def retrieval_queries_for_mode(assistant_mode: str | None) -> list[str]:
    key = (assistant_mode or "").strip().lower()
    role_queries = ROLE_RETRIEVAL_QUERIES.get(key, ROLE_RETRIEVAL_QUERIES["developer"])
    # Role-specific queries first so they win the per-chunk budget, then the
    # shared baseline that every project benefits from.
    ordered = role_queries + BASE_RETRIEVAL_QUERIES
    seen: set[str] = set()
    deduped: list[str] = []
    for query in ordered:
        if query not in seen:
            seen.add(query)
            deduped.append(query)
    return deduped


PER_QUERY_LIMIT = 4
MAX_CHUNKS = 12
MAX_TOTAL_CHARS = 12000
MAX_RISKS = 8
MAX_START_HERE = 4
MAX_RUN_COMMANDS = 5


@dataclass(frozen=True)
class GenerateProjectUnderstandingInput:
    workspace_id: str


class GenerateProjectUnderstandingNotFoundError(ValueError):
    pass


class GenerateProjectUnderstandingValidationError(ValueError):
    pass


class GenerateProjectUnderstandingUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        llm_provider_factory: LLMProviderFactoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        selection_repository: WorkspaceModelSelectionRepositoryPort,
        understanding_repository: ProjectUnderstandingRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.llm_provider_factory = llm_provider_factory
        self.index_status_repository = index_status_repository
        self.selection_repository = selection_repository
        self.understanding_repository = understanding_repository

    def execute(
        self,
        request: GenerateProjectUnderstandingInput,
    ) -> ProjectUnderstanding:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise GenerateProjectUnderstandingNotFoundError("Workspace not found")

        index_status = self.index_status_repository.get(request.workspace_id)
        if index_status is None or index_status.status != "indexed":
            raise GenerateProjectUnderstandingValidationError(
                "This workspace has not been indexed yet. Run workspace indexing "
                "first."
            )

        llm_provider = self._resolve_selected_llm(request.workspace_id)

        context_results = self._retrieve_context(
            request.workspace_id, workspace.assistant_mode
        )
        if not context_results:
            raise GenerateProjectUnderstandingValidationError(
                "No indexed context was found for this workspace. Reindex the "
                "workspace and try again."
            )

        prompt = build_project_understanding_prompt(
            context_results=context_results,
            assistant_mode=workspace.assistant_mode,
            max_risks=MAX_RISKS,
        )
        try:
            raw_answer = llm_provider.generate(prompt)
        except RuntimeError as exc:
            raise GenerateProjectUnderstandingValidationError(
                "The selected local model could not generate a project "
                f"understanding right now: {exc}"
            ) from exc

        used_paths = list(
            dict.fromkeys(result.source_path for result in context_results)
        )
        parsed = self._parse_understanding(raw_answer, used_paths)

        model_label = self._model_label(llm_provider)
        understanding = ProjectUnderstanding(
            workspace_id=request.workspace_id,
            model=model_label,
            generated_at=datetime.now().astimezone().isoformat(),
            index_signature=self._index_signature(request.workspace_id, used_paths),
            summary=parsed["summary"],
            risks=parsed["risks"],
            sources=used_paths,
            architecture=parsed["architecture"],
            start_here=parsed["start_here"],
            run_commands=parsed["run_commands"],
        )
        return self.understanding_repository.save(understanding)

    def _resolve_selected_llm(self, workspace_id: str) -> LLMProviderPort:
        selection = self.selection_repository.get(workspace_id)
        selected_llm = selection.selected_llm if selection is not None else None
        if selected_llm is None:
            raise GenerateProjectUnderstandingValidationError(
                "No selected LLM is configured for this workspace."
            )
        if not self.llm_provider_factory.supports(selected_llm.provider):
            raise GenerateProjectUnderstandingValidationError(
                f"Unsupported selected LLM provider: {selected_llm.provider}"
            )
        try:
            return self.llm_provider_factory.create(
                provider=selected_llm.provider,
                model=selected_llm.model,
            )
        except LLMProviderFactoryError as exc:
            raise GenerateProjectUnderstandingValidationError(str(exc)) from exc

    def _retrieve_context(
        self, workspace_id: str, assistant_mode: str | None = None
    ) -> list[ContextSearchResult]:
        collected: dict[str, ContextSearchResult] = {}
        total_chars = 0
        for query in retrieval_queries_for_mode(assistant_mode):
            query_embedding = self.embedding_provider.embed_text(query)
            results = self.vector_store.search(
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                limit=PER_QUERY_LIMIT,
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=len(query_embedding),
            )
            for result in results:
                if result.source_path in collected:
                    continue
                if len(collected) >= MAX_CHUNKS:
                    break
                if total_chars + len(result.content) > MAX_TOTAL_CHARS:
                    continue
                collected[result.source_path] = result
                total_chars += len(result.content)
            if len(collected) >= MAX_CHUNKS:
                break
        return list(collected.values())

    def _parse_understanding(
        self,
        raw_answer: str,
        used_paths: list[str],
    ) -> dict:
        payload = _extract_json_object(raw_answer)
        if not isinstance(payload, dict):
            # Robust fallback: keep the raw text as the summary, nothing else.
            return {
                "summary": raw_answer.strip(),
                "risks": [],
                "architecture": "",
                "start_here": [],
                "run_commands": [],
            }

        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = raw_answer.strip()

        risks: list[ProjectRisk] = []
        raw_risks = payload.get("risks")
        if isinstance(raw_risks, list):
            for entry in raw_risks:
                if not isinstance(entry, dict):
                    continue
                text = entry.get("text")
                if not isinstance(text, str) or not text.strip():
                    continue
                source_file = entry.get("file")
                if not isinstance(source_file, str) or not source_file.strip():
                    source_file = None
                elif source_file not in used_paths:
                    # Only keep citations that actually came from retrieved files.
                    source_file = None
                risks.append(
                    ProjectRisk(text=text.strip(), source_file=source_file)
                )
                if len(risks) >= MAX_RISKS:
                    break

        architecture = payload.get("architecture")
        if not isinstance(architecture, str):
            architecture = ""

        return {
            "summary": summary.strip(),
            "risks": risks,
            "architecture": architecture.strip(),
            "start_here": self._parse_start_here(payload.get("start_here"), used_paths),
            "run_commands": self._parse_run_commands(payload.get("run_commands")),
        }

    @staticmethod
    def _parse_start_here(
        raw: object, used_paths: list[str]
    ) -> list[ProjectStartPoint]:
        points: list[ProjectStartPoint] = []
        if not isinstance(raw, list):
            return points
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            file = entry.get("file")
            reason = entry.get("reason")
            if not isinstance(file, str) or file.strip() not in used_paths:
                # Only keep reading-order entries that point at a real source path.
                continue
            reason_text = reason.strip() if isinstance(reason, str) else ""
            points.append(ProjectStartPoint(file=file.strip(), reason=reason_text))
            if len(points) >= MAX_START_HERE:
                break
        return points

    @staticmethod
    def _parse_run_commands(raw: object) -> list[ProjectRunCommand]:
        commands: list[ProjectRunCommand] = []
        if not isinstance(raw, list):
            return commands
        seen: set[str] = set()
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            command = entry.get("command")
            if not isinstance(command, str) or not command.strip():
                continue
            normalized = command.strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            note = entry.get("note")
            note_text = note.strip() if isinstance(note, str) else ""
            commands.append(ProjectRunCommand(command=normalized, note=note_text))
            if len(commands) >= MAX_RUN_COMMANDS:
                break
        return commands

    def _model_label(self, llm_provider: LLMProviderPort) -> str:
        model = llm_provider.model_name or ""
        if model:
            return f"{llm_provider.provider_name}/{model}"
        return llm_provider.provider_name

    def _index_signature(self, workspace_id: str, used_paths: list[str]) -> str:
        index_status = self.index_status_repository.get(workspace_id)
        if index_status is not None and index_status.last_indexed_at:
            base = (
                f"{index_status.last_indexed_at}|"
                f"{index_status.indexed_files_count}|"
                f"{index_status.chunks_count}"
            )
        else:
            base = datetime.now().astimezone().isoformat()
        digest = hashlib.sha256(
            (base + "|" + "|".join(sorted(used_paths))).encode("utf-8")
        ).hexdigest()
        return digest[:16]


def _extract_json_object(text: str) -> object:
    """Best-effort extraction of the first JSON object from a model response.

    Strips ```json code fences and falls back to the first ``{...}`` span. Returns
    ``None`` when nothing parseable is found.
    """

    if not text:
        return None
    stripped = text.strip()
    # Remove surrounding code fences if present.
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()
    try:
        return json.loads(stripped)
    except (ValueError, TypeError):
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = stripped[start : end + 1]
        try:
            return json.loads(candidate)
        except (ValueError, TypeError):
            return None
    return None
