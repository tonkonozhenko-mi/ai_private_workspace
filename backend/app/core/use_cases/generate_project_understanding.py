import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.project_understanding import ProjectRisk, ProjectUnderstanding
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


# Small, fixed set of retrieval queries that together cover the most useful lenses
# for a grounded project understanding. Each is embedded and searched separately;
# the resulting chunks are deduped by source path and budgeted before prompting.
RETRIEVAL_QUERIES = [
    "architecture and what this project does",
    "deployment and infrastructure",
    "configuration and environment",
    "tests",
    "risks, TODOs, missing pieces",
]
PER_QUERY_LIMIT = 4
MAX_CHUNKS = 12
MAX_TOTAL_CHARS = 12000
MAX_RISKS = 8


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

        context_results = self._retrieve_context(request.workspace_id)
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
        summary, risks = self._parse_understanding(raw_answer, used_paths)

        model_label = self._model_label(llm_provider)
        understanding = ProjectUnderstanding(
            workspace_id=request.workspace_id,
            model=model_label,
            generated_at=datetime.now().astimezone().isoformat(),
            index_signature=self._index_signature(request.workspace_id, used_paths),
            summary=summary,
            risks=risks,
            sources=used_paths,
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

    def _retrieve_context(self, workspace_id: str) -> list[ContextSearchResult]:
        collected: dict[str, ContextSearchResult] = {}
        total_chars = 0
        for query in RETRIEVAL_QUERIES:
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
    ) -> tuple[str, list[ProjectRisk]]:
        payload = _extract_json_object(raw_answer)
        if not isinstance(payload, dict):
            # Robust fallback: keep the raw text as the summary, no risks.
            return raw_answer.strip(), []

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
        return summary.strip(), risks

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
