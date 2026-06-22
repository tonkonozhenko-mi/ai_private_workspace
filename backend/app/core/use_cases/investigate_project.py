"""Read-only Investigator agent use case.

Runs a bounded ReAct loop: the local model repeatedly picks one read-only tool,
reads the result, and continues until it can answer. Tools only ever READ — they
search the index, read files, query the project graph, or list files. Nothing is
written or executed. Sources are collected deterministically from the tools the
agent actually used, so the answer is always backed by real evidence even if the
model forgets to cite.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.core.domain.investigator import (
    AgentStep,
    InvestigationResult,
    ToolSpec,
    build_investigator_prompt,
    parse_agent_step,
)
from app.core.domain.role_lens import role_lens_for
from app.core.ports.embedding_provider import EmbeddingProviderPort
from app.core.ports.file_system import FileSystemPort
from app.core.ports.git_history import GitHistoryPort
from app.core.ports.llm_provider_factory import LLMProviderFactoryError, LLMProviderFactoryPort
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.search_workspace_context import (
    SearchWorkspaceContextInput,
    SearchWorkspaceContextUseCase,
)

_MAX_OBSERVATION_CHARS = 1200
_MAX_FILE_CHARS = 1600
_MAX_INVALID_RETRIES = 2


@dataclass(frozen=True)
class InvestigateProjectInput:
    workspace_id: str
    question: str
    role: str | None = None
    max_steps: int = 8


class InvestigateProjectWorkspaceNotFoundError(ValueError):
    pass


class InvestigateProjectError(RuntimeError):
    pass


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + " …(truncated)"


class InvestigateProjectUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        llm_provider_factory: LLMProviderFactoryPort,
        embedding_provider: EmbeddingProviderPort,
        vector_store: VectorStorePort,
        file_system: FileSystemPort,
        project_graph_repository: ProjectGraphRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        git_history: GitHistoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.llm_provider_factory = llm_provider_factory
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.file_system = file_system
        self.project_graph_repository = project_graph_repository
        self.project_scan_repository = project_scan_repository
        self.git_history = git_history

    def execute(self, request: InvestigateProjectInput) -> InvestigationResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise InvestigateProjectWorkspaceNotFoundError("Workspace not found")

        try:
            provider = self.llm_provider_factory.create(provider=None, model=None)
        except (LLMProviderFactoryError, RuntimeError) as exc:
            raise InvestigateProjectError(str(exc)) from exc

        tools, tool_specs = self._build_tools(request.workspace_id, workspace.project_path)
        allowed = set(tools.keys())
        role_label = role_lens_for(request.role or "developer").label

        steps: list[AgentStep] = []
        sources: list[str] = []
        invalid_streak = 0

        def add_sources(new: list[str]) -> None:
            for s in new:
                if s and s not in sources:
                    sources.append(s)

        for _ in range(max(1, request.max_steps)):
            prompt = build_investigator_prompt(
                request.question, tool_specs, steps, role_label
            )
            try:
                text = provider.generate(prompt, temperature=0.0)
            except (RuntimeError, ValueError) as exc:
                raise InvestigateProjectError(str(exc)) from exc

            decision = parse_agent_step(text, allowed)

            if decision.kind == "final":
                return InvestigationResult(
                    answer=decision.answer,
                    steps=steps,
                    sources=sources,
                    used_steps=len(steps),
                    stopped_reason="answered",
                )

            if decision.kind == "invalid":
                invalid_streak += 1
                if invalid_streak > _MAX_INVALID_RETRIES:
                    break
                steps.append(
                    AgentStep(
                        thought=decision.thought,
                        tool="(format)",
                        tool_input="",
                        observation=f"Reply was not valid: {decision.error}",
                    )
                )
                continue

            invalid_streak = 0
            observation, new_sources = tools[decision.tool](decision.tool_input)
            add_sources(new_sources)
            steps.append(
                AgentStep(
                    thought=decision.thought,
                    tool=decision.tool,
                    tool_input=decision.tool_input,
                    observation=_truncate(observation, _MAX_OBSERVATION_CHARS),
                )
            )

        # Out of steps: force a final answer from what was gathered.
        answer = self._forced_final(provider, request.question, tool_specs, steps, role_label)
        return InvestigationResult(
            answer=answer,
            steps=steps,
            sources=sources,
            used_steps=len(steps),
            stopped_reason="budget_exhausted",
        )

    def _forced_final(self, provider, question, tool_specs, steps, role_label) -> str:
        prompt = (
            build_investigator_prompt(question, tool_specs, steps, role_label)
            + "\n\nYou have no steps left. Give your FINAL answer now using ONLY the "
            "observations above. If they are insufficient, say what is and isn't "
            "visible in the project.\nFINAL:"
        )
        try:
            text = provider.generate(prompt, temperature=0.0)
        except (RuntimeError, ValueError):
            return (
                "I couldn't reach a confident answer within the step budget. "
                "See the steps above for what was found."
            )
        decision = parse_agent_step("FINAL: " + text, set())
        return decision.answer or text.strip()

    # -- tools (all read-only) ---------------------------------------------

    def _build_tools(
        self, workspace_id: str, project_path: str
    ) -> tuple[dict[str, Callable[[str], tuple[str, list[str]]]], list[ToolSpec]]:
        def search_code(query: str) -> tuple[str, list[str]]:
            query = query.strip()
            if not query:
                return "Provide a search query.", []
            try:
                results = SearchWorkspaceContextUseCase(
                    self.workspace_repository, self.embedding_provider, self.vector_store
                ).execute(
                    SearchWorkspaceContextInput(workspace_id=workspace_id, query=query, limit=5)
                )
            except Exception as exc:  # noqa: BLE001 - a tool failure must not crash the agent
                return f"search_code failed: {exc}", []
            if not results:
                return "No indexed matches (the project may not be indexed yet).", []
            lines = []
            sources = []
            for r in results:
                snippet = " ".join(r.content.split())[:200]
                lines.append(f"- {r.source_path}: {snippet}")
                sources.append(r.source_path)
            return "\n".join(lines), sources

        def read_file(path: str) -> tuple[str, list[str]]:
            path = path.strip().strip("\"'")
            if not path:
                return "Provide a file path.", []
            try:
                content = self.file_system.read_text_file(
                    root_path=project_path, relative_path=path
                )
            except Exception as exc:  # noqa: BLE001
                return f"Could not read {path}: {exc}", []
            if not content:
                return f"{path} is empty or could not be read.", []
            return _truncate(content, _MAX_FILE_CHARS), [path]

        def graph_query(query: str) -> tuple[str, list[str]]:
            graph = self.project_graph_repository.get_latest_graph(workspace_id)
            if graph is None:
                return "No project map has been built yet (use Build first).", []
            q = query.strip().lower()
            if not q or q == "all":
                counts: dict[str, int] = {}
                for e in graph.entities:
                    counts[e.type] = counts.get(e.type, 0) + 1
                summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
                return f"Graph contains — {summary or 'nothing'}.", []
            matched = [
                e for e in graph.entities if q in e.name.lower() or q in e.type.lower()
            ][:8]
            if not matched:
                return f"No graph entities match '{query}'.", []
            lines = []
            sources = []
            ids = {e.id for e in matched}
            for e in matched:
                rels = [
                    f"{r.relation_type}->{r.target_entity_id.split(':',1)[-1]}"
                    for r in graph.relations
                    if r.source_entity_id == e.id
                ][:5]
                lines.append(
                    f"- {e.name} ({e.type})"
                    + (f" [{', '.join(rels)}]" if rels else "")
                    + (f" — {e.source_file}" if e.source_file else "")
                )
                if e.source_file:
                    sources.append(e.source_file)
            related_findings = [
                f.title for f in graph.findings if any(i in (f.source_file or "") for i in ids)
            ]
            if related_findings:
                lines.append("findings: " + "; ".join(related_findings[:3]))
            return "\n".join(lines), sources

        def list_files(substring: str) -> tuple[str, list[str]]:
            scan = self.project_scan_repository.get_latest_scan(workspace_id)
            if scan is None or not getattr(scan, "files", None):
                return "No scan available; nothing to list.", []
            sub = substring.strip().lower()
            paths = [f.path for f in scan.files]
            if sub:
                hits = [p for p in paths if sub in p.lower()][:30]
                if not hits:
                    return f"No files match '{substring}'.", []
                return "\n".join(hits), []
            top = sorted({p.split("/", 1)[0] for p in paths})[:40]
            return "Top-level entries: " + ", ".join(top), []

        def git_history(path: str) -> tuple[str, list[str]]:
            path = path.strip().strip("\"'")
            try:
                activity = self.git_history.file_activity(project_path, path or None)
            except Exception as exc:  # noqa: BLE001
                return f"git_history failed: {exc}", []
            if activity is None:
                return "Not a git repository (or git is unavailable).", []
            lines = [
                f"{activity.path or 'Repository'}: {activity.total_commits} commit(s)"
            ]
            if activity.top_authors:
                lines.append(
                    "Top authors: "
                    + ", ".join(f"{a.name} ({a.commits})" for a in activity.top_authors)
                )
            for commit in activity.recent_commits[:6]:
                when = commit.committed_at[:10]
                lines.append(f"- {commit.short_hash} {commit.subject} — {commit.author} ({when})")
            return "\n".join(lines), ([activity.path] if activity.path else [])

        def ci_triggers(_: str) -> tuple[str, list[str]]:
            from app.core.domain.project_intelligence_view import present_ci

            graph = self.project_graph_repository.get_latest_graph(workspace_id)
            if graph is None:
                return "No project map has been built yet (use Build first).", []
            ci = present_ci(graph)
            if not ci.get("has_data"):
                return "No CI/CD trigger information detected (GitHub Actions only).", []
            lines = []
            for scenario in ci["scenarios"]:
                names = ", ".join(w["name"] for w in scenario["workflows"])
                lines.append(f"{scenario['label']}: {names}")
            return "\n".join(lines), []

        tools = {
            "search_code": search_code,
            "read_file": read_file,
            "graph_query": graph_query,
            "list_files": list_files,
            "git_history": git_history,
            "ci_triggers": ci_triggers,
        }
        specs = [
            ToolSpec("search_code", "search_code: <query>", "semantic search over the indexed code/docs"),
            ToolSpec("read_file", "read_file: <relative/path>", "read a project file's contents"),
            ToolSpec(
                "graph_query",
                "graph_query: <name|type|all>",
                "look up entities/relations in the project map",
            ),
            ToolSpec("list_files", "list_files: <substring>", "list project files matching a substring"),
            ToolSpec(
                "git_history",
                "git_history: <relative/path or empty>",
                "who changed a file and its recent commits (empty = whole repo)",
            ),
            ToolSpec(
                "ci_triggers",
                "ci_triggers: (no input)",
                "what CI workflows run on push / pull request / tag / schedule",
            ),
        ]
        return tools, specs
