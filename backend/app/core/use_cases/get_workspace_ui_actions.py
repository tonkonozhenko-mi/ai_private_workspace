from dataclasses import dataclass

from app.core.domain.workspace_ui_actions import (
    WorkspaceUIAction,
    WorkspaceUIActionCatalog,
)
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.get_workspace_models_dashboard_summary import (
    GetWorkspaceModelsDashboardSummaryInput,
    GetWorkspaceModelsDashboardSummaryUseCase,
)
from app.core.use_cases.get_workspace_quick_start import (
    GetWorkspaceQuickStartInput,
    GetWorkspaceQuickStartUseCase,
)
from app.core.use_cases.get_workspace_readiness import (
    GetWorkspaceReadinessInput,
    GetWorkspaceReadinessUseCase,
)


@dataclass(frozen=True)
class GetWorkspaceUIActionsInput:
    workspace_id: str


class WorkspaceUIActionsNotFoundError(ValueError):
    pass


class GetWorkspaceUIActionsUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        quick_start_use_case: GetWorkspaceQuickStartUseCase,
        readiness_use_case: GetWorkspaceReadinessUseCase,
        models_summary_use_case: GetWorkspaceModelsDashboardSummaryUseCase,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.quick_start_use_case = quick_start_use_case
        self.readiness_use_case = readiness_use_case
        self.models_summary_use_case = models_summary_use_case

    def execute(self, request: GetWorkspaceUIActionsInput) -> WorkspaceUIActionCatalog:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise WorkspaceUIActionsNotFoundError("Workspace not found")

        quick_start = self.quick_start_use_case.execute(
            GetWorkspaceQuickStartInput(workspace_id=request.workspace_id)
        )
        readiness = self.readiness_use_case.execute(
            GetWorkspaceReadinessInput(workspace_id=request.workspace_id)
        )
        models_summary = self.models_summary_use_case.execute(
            GetWorkspaceModelsDashboardSummaryInput(workspace_id=request.workspace_id)
        )
        primary_action_id = self._primary_action_id(
            quick_start.next_action_id,
            models_summary.primary_next_action_id,
        )
        actions = self._actions(
            workspace_id=request.workspace_id,
            primary_action_id=primary_action_id,
            quick_start_next_action_id=quick_start.next_action_id,
            readiness=readiness,
            models_summary=models_summary,
        )

        return WorkspaceUIActionCatalog(
            workspace_id=request.workspace_id,
            primary_action_id=primary_action_id,
            actions=actions,
            notes=[
                "UI actions are deterministic metadata and are never executed.",
                "Mutation flags describe the target endpoint, not this catalog request.",
                "The catalog performs no runtime health checks or provider calls.",
            ],
        )

    def _actions(
        self,
        *,
        workspace_id: str,
        primary_action_id: str | None,
        quick_start_next_action_id: str | None,
        readiness,
        models_summary,
    ) -> list[WorkspaceUIAction]:
        command_suggestions_available = self._capability_available(
            readiness,
            "command_suggestions",
        )
        model_setup_needed = models_summary.overall_status != "ready"

        return [
            self._action(
                id="scan_project",
                title="Scan project",
                description="Detect project files, technologies, and skills.",
                method="POST",
                endpoint=f"/workspaces/{workspace_id}/scan",
                category="setup",
                status=(
                    "recommended" if quick_start_next_action_id == "scan_project" else "available"
                ),
                primary_action_id=primary_action_id,
                mutates_data=True,
                reason=(
                    "Project scan is the next recommended setup action."
                    if quick_start_next_action_id == "scan_project"
                    else "Project scan can be refreshed at any time."
                ),
            ),
            self._action(
                id="index_workspace",
                title="Index workspace",
                description="Build searchable workspace context from the latest scan.",
                method="POST",
                endpoint=f"/workspaces/{workspace_id}/index",
                category="setup",
                status=(
                    "blocked"
                    if not readiness.can_index
                    else (
                        "recommended"
                        if quick_start_next_action_id == "index_workspace"
                        else "available"
                    )
                ),
                primary_action_id=primary_action_id,
                mutates_data=True,
                reason=(
                    "Run a project scan before indexing."
                    if not readiness.can_index
                    else (
                        "Workspace indexing is the next recommended setup action."
                        if quick_start_next_action_id == "index_workspace"
                        else "Workspace context can be indexed or refreshed."
                    )
                ),
            ),
            self._action(
                id="project_overview",
                title="Generate project overview",
                description="Generate a deterministic project overview report.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/reports/project-overview",
                category="project",
                status="optional" if readiness.can_analyze else "blocked",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason=(
                    "A project overview is available from the latest scan."
                    if readiness.can_analyze
                    else "Run a project scan before generating a project overview."
                ),
            ),
            self._action(
                id="ask_workspace",
                title="Ask workspace",
                description="Ask a question using active indexed workspace context.",
                method="POST",
                endpoint=f"/workspaces/{workspace_id}/ask",
                category="ask",
                status=(
                    "blocked"
                    if not readiness.can_ask
                    else (
                        "recommended"
                        if quick_start_next_action_id == "ask_first_question"
                        else "available"
                    )
                ),
                primary_action_id=primary_action_id,
                mutates_data=True,
                reason=(
                    "Index workspace context before asking questions."
                    if not readiness.can_ask
                    else (
                        "Asking a workspace question is the next recommended action."
                        if quick_start_next_action_id == "ask_first_question"
                        else "Active indexed context is ready for workspace questions."
                    )
                ),
            ),
            self._action(
                id="ask_selected_llm",
                title="Ask using selected LLM",
                description="Ask a workspace question using the persisted selected LLM.",
                method="POST",
                endpoint=f"/workspaces/{workspace_id}/ask-selected",
                category="ask",
                status=(
                    "blocked"
                    if not models_summary.can_ask_with_selected_llm
                    else (
                        "recommended"
                        if models_summary.primary_next_action_id == "ask_with_selected_llm"
                        else "available"
                    )
                ),
                primary_action_id=primary_action_id,
                mutates_data=True,
                reason=(
                    "Select a supported workspace LLM before using this action."
                    if not models_summary.can_ask_with_selected_llm
                    else "The selected LLM is available through per-request override."
                ),
            ),
            self._action(
                id="models_dashboard",
                title="Open models dashboard",
                description="Review detailed workspace model state and recommendations.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/models/dashboard",
                category="models",
                status="available",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason="Detailed workspace model diagnostics are available.",
            ),
            self._action(
                id="models_dashboard_summary",
                title="Open models summary",
                description="Review compact workspace model status and next action.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/models/dashboard/summary",
                category="models",
                status="available",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason="Compact workspace model status is available.",
            ),
            self._action(
                id="model_selection",
                title="Review model selection",
                description="Review selected workspace LLM and embedding preferences.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/models/selection",
                category="models",
                status="available",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason="Workspace model preference state is available.",
            ),
            self._action(
                id="model_usage_plan",
                title="Review selected model usage",
                description="Review how selected models can be used by the workspace.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/models/usage-plan",
                category="models",
                status="available",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason="Selected-model usage guidance is available.",
            ),
            self._action(
                id="local_ai_activation_guide",
                title="Review local AI activation guide",
                description="Review instructions for activating selected local AI models.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/local-ai/activation-guide",
                category="models",
                status="recommended" if model_setup_needed else "optional",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason=(
                    "Selected model setup needs attention."
                    if model_setup_needed
                    else "Selected model setup is ready; activation guidance is optional."
                ),
            ),
            self._action(
                id="command_suggestions",
                title="Review command suggestions",
                description="Review deterministic command templates for this workspace.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/commands/suggestions",
                category="commands",
                status="optional" if command_suggestions_available else "blocked",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason=(
                    "Skill-based command suggestions are available."
                    if command_suggestions_available
                    else "Run a project scan before reviewing command suggestions."
                ),
            ),
            self._action(
                id="timeline",
                title="View workspace timeline",
                description="Review recent persisted workspace activity.",
                method="GET",
                endpoint=f"/workspaces/{workspace_id}/timeline?limit=20",
                category="timeline",
                status="available",
                primary_action_id=primary_action_id,
                mutates_data=False,
                reason="Workspace activity history is available.",
            ),
        ]

    @staticmethod
    def _action(
        *,
        id: str,
        title: str,
        description: str,
        method: str,
        endpoint: str,
        category: str,
        status: str,
        primary_action_id: str | None,
        mutates_data: bool,
        reason: str,
    ) -> WorkspaceUIAction:
        is_primary = id == primary_action_id
        if is_primary and status != "blocked":
            status = "recommended"
        return WorkspaceUIAction(
            id=id,
            title=title,
            description=description,
            method=method,
            endpoint=endpoint,
            category=category,
            status=status,
            is_primary=is_primary,
            mutates_data=mutates_data,
            reason=reason,
        )

    @staticmethod
    def _primary_action_id(
        quick_start_action_id: str | None,
        models_action_id: str | None,
    ) -> str | None:
        quick_start_mapping = {
            "scan_project": "scan_project",
            "index_workspace": "index_workspace",
            "ask_first_question": "ask_workspace",
        }
        primary_action_id = quick_start_mapping.get(quick_start_action_id)
        if (
            primary_action_id == "ask_workspace"
            and models_action_id == "restart_backend_for_embedding"
        ):
            return "local_ai_activation_guide"
        return primary_action_id

    @staticmethod
    def _capability_available(readiness, capability_id: str) -> bool:
        return any(
            capability.id == capability_id and capability.available
            for capability in readiness.capabilities
        )
