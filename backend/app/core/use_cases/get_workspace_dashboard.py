from dataclasses import dataclass

from app.core.domain.workspace_dashboard import WorkspaceDashboard
from app.core.use_cases.get_runtime_health import GetRuntimeHealthUseCase
from app.core.use_cases.get_workspace_assistant_recommendation import (
    GetWorkspaceAssistantRecommendationInput,
    GetWorkspaceAssistantRecommendationUseCase,
)
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
from app.core.use_cases.get_workspace_summary import (
    GetWorkspaceSummaryInput,
    GetWorkspaceSummaryUseCase,
    WorkspaceSummaryNotFoundError,
)
from app.core.use_cases.list_workspace_timeline import (
    ListWorkspaceTimelineInput,
    ListWorkspaceTimelineUseCase,
)


@dataclass(frozen=True)
class GetWorkspaceDashboardInput:
    workspace_id: str


class WorkspaceDashboardNotFoundError(ValueError):
    pass


class GetWorkspaceDashboardUseCase:
    def __init__(
        self,
        summary_use_case: GetWorkspaceSummaryUseCase,
        readiness_use_case: GetWorkspaceReadinessUseCase,
        quick_start_use_case: GetWorkspaceQuickStartUseCase,
        assistant_recommendation_use_case: GetWorkspaceAssistantRecommendationUseCase,
        timeline_use_case: ListWorkspaceTimelineUseCase,
        runtime_health_use_case: GetRuntimeHealthUseCase,
        models_summary_use_case: GetWorkspaceModelsDashboardSummaryUseCase,
    ) -> None:
        self.summary_use_case = summary_use_case
        self.readiness_use_case = readiness_use_case
        self.quick_start_use_case = quick_start_use_case
        self.assistant_recommendation_use_case = assistant_recommendation_use_case
        self.timeline_use_case = timeline_use_case
        self.runtime_health_use_case = runtime_health_use_case
        self.models_summary_use_case = models_summary_use_case

    def execute(self, request: GetWorkspaceDashboardInput) -> WorkspaceDashboard:
        try:
            summary = self.summary_use_case.execute(
                GetWorkspaceSummaryInput(workspace_id=request.workspace_id)
            )
        except WorkspaceSummaryNotFoundError as exc:
            raise WorkspaceDashboardNotFoundError(str(exc)) from exc

        readiness = self.readiness_use_case.execute(
            GetWorkspaceReadinessInput(workspace_id=request.workspace_id)
        )
        quick_start = self.quick_start_use_case.execute(
            GetWorkspaceQuickStartInput(workspace_id=request.workspace_id)
        )
        assistant_recommendation = self.assistant_recommendation_use_case.execute(
            GetWorkspaceAssistantRecommendationInput(workspace_id=request.workspace_id)
        )
        recent_events = self.timeline_use_case.execute(
            ListWorkspaceTimelineInput(workspace_id=request.workspace_id, limit=5)
        )
        runtime_health = self.runtime_health_use_case.execute()
        models_summary = self.models_summary_use_case.execute(
            GetWorkspaceModelsDashboardSummaryInput(workspace_id=request.workspace_id)
        )

        return WorkspaceDashboard(
            workspace_id=summary.workspace_id,
            workspace_name=summary.name,
            assistant_mode=summary.assistant_mode,
            status=readiness.status,
            summary=summary,
            readiness=readiness,
            quick_start=quick_start,
            assistant_recommendation=assistant_recommendation,
            recent_events=recent_events,
            runtime_health=runtime_health,
            primary_next_action_id=quick_start.next_action_id,
            primary_next_action_title=quick_start.next_action_title,
            models_summary=models_summary,
        )
