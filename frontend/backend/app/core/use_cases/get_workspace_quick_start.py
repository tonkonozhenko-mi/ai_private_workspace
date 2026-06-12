from dataclasses import dataclass

from app.core.domain.workspace_quick_start import QuickStartStep, WorkspaceQuickStart
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceQuickStartInput:
    workspace_id: str


class WorkspaceQuickStartNotFoundError(ValueError):
    pass


class GetWorkspaceQuickStartUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        project_scan_repository: ProjectScanRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        configuration: dict[str, str],
    ) -> None:
        self.workspace_repository = workspace_repository
        self.project_scan_repository = project_scan_repository
        self.index_status_repository = index_status_repository
        self.configuration = configuration

    def execute(self, request: GetWorkspaceQuickStartInput) -> WorkspaceQuickStart:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise WorkspaceQuickStartNotFoundError("Workspace not found")

        has_scan = (
            self.project_scan_repository.get_latest_scan(request.workspace_id)
            is not None
        )
        index_status = self.index_status_repository.get(request.workspace_id)
        is_indexed = bool(
            has_scan and index_status is not None and index_status.status == "indexed"
        )
        llm_provider = self.configuration.get("LLM_PROVIDER", "").lower()
        vector_store = self.configuration.get("VECTOR_STORE", "").lower()
        has_real_llm = bool(llm_provider and llm_provider != "fake")
        has_persistent_vector_store = bool(
            vector_store and vector_store != "memory"
        )

        status = self._status(
            has_scan=has_scan,
            is_indexed=is_indexed,
            has_real_llm=has_real_llm,
            has_persistent_vector_store=has_persistent_vector_store,
        )
        next_action_id, next_action_title = self._next_action(
            has_scan=has_scan,
            is_indexed=is_indexed,
        )
        return WorkspaceQuickStart(
            workspace_id=request.workspace_id,
            status=status,
            next_action_id=next_action_id,
            next_action_title=next_action_title,
            steps=self._steps(
                workspace_id=request.workspace_id,
                has_scan=has_scan,
                is_indexed=is_indexed,
                has_real_llm=has_real_llm,
                has_persistent_vector_store=has_persistent_vector_store,
            ),
            notes=self._notes(
                has_real_llm=has_real_llm,
                has_persistent_vector_store=has_persistent_vector_store,
            ),
        )

    @staticmethod
    def _status(
        has_scan: bool,
        is_indexed: bool,
        has_real_llm: bool,
        has_persistent_vector_store: bool,
    ) -> str:
        if not has_scan:
            return "new"
        if not is_indexed:
            return "scanned"
        if has_real_llm and has_persistent_vector_store:
            return "ready"
        return "indexed"

    @staticmethod
    def _next_action(has_scan: bool, is_indexed: bool) -> tuple[str, str]:
        if not has_scan:
            return "scan_project", "Run project scan"
        if not is_indexed:
            return "index_workspace", "Index workspace context"
        return "ask_first_question", "Ask first workspace question"

    @staticmethod
    def _steps(
        workspace_id: str,
        has_scan: bool,
        is_indexed: bool,
        has_real_llm: bool,
        has_persistent_vector_store: bool,
    ) -> list[QuickStartStep]:
        real_runtime_configured = has_real_llm and has_persistent_vector_store
        return [
            QuickStartStep(
                id="runtime_setup",
                title="Review runtime setup",
                description=(
                    "Review configured providers and optional local runtime upgrades."
                ),
                status="done" if real_runtime_configured else "optional",
                action_id="review_runtime_setup",
                endpoint="POST /runtime/setup-guide",
            ),
            QuickStartStep(
                id="scan_project",
                title="Run project scan",
                description="Detect project files, technologies, and skills.",
                status="done" if has_scan else "next",
                action_id="scan_project",
                endpoint=f"POST /workspaces/{workspace_id}/scan",
            ),
            QuickStartStep(
                id="review_detected_skills",
                title="Review detected skills",
                description="Review the deterministic skills found by the project scan.",
                status="done" if has_scan else "blocked",
                action_id="review_detected_skills" if has_scan else None,
                endpoint=f"GET /workspaces/{workspace_id}/summary",
            ),
            QuickStartStep(
                id="index_workspace",
                title="Index workspace context",
                description="Build searchable context from the latest project scan.",
                status=(
                    "done"
                    if is_indexed
                    else "next"
                    if has_scan
                    else "blocked"
                ),
                action_id="index_workspace" if has_scan else None,
                endpoint=f"POST /workspaces/{workspace_id}/index",
            ),
            QuickStartStep(
                id="ask_first_question",
                title="Ask first workspace question",
                description="Ask a question using indexed workspace context.",
                status="next" if is_indexed else "blocked",
                action_id="ask_first_question" if is_indexed else None,
                endpoint=f"POST /workspaces/{workspace_id}/ask",
            ),
            QuickStartStep(
                id="generate_project_overview",
                title="Generate project overview",
                description="Generate a deterministic overview from scan and analysis data.",
                status="optional" if has_scan else "blocked",
                action_id="generate_project_overview" if has_scan else None,
                endpoint=(
                    f"GET /workspaces/{workspace_id}/reports/project-overview"
                ),
            ),
        ]

    @staticmethod
    def _notes(
        has_real_llm: bool,
        has_persistent_vector_store: bool,
    ) -> list[str]:
        notes = [
            "Quick Start reads persisted state only and never runs workspace actions."
        ]
        if not has_persistent_vector_store:
            notes.append(
                "The in-memory vector store loses context after API restart; "
                "reindex the workspace when needed."
            )
        if not has_real_llm:
            notes.append(
                "Workspace answers use the fake LLM provider until a real local "
                "LLM provider such as Ollama is enabled."
            )
        return notes
