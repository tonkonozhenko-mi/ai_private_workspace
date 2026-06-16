from pydantic import BaseModel

from app.api.schemas.assistant_profile_schemas import (
    WorkspaceAssistantRecommendationResponse,
    to_workspace_assistant_recommendation_response,
)
from app.api.schemas.runtime_health_schemas import (
    RuntimeHealthResponse,
    to_runtime_health_response,
)
from app.api.schemas.timeline_schemas import (
    TimelineEventResponse,
    to_timeline_event_response,
)
from app.api.schemas.workspace_models_dashboard_summary_schemas import (
    WorkspaceModelsDashboardSummaryResponse,
    to_workspace_models_dashboard_summary_response,
)
from app.api.schemas.workspace_quick_start_schemas import (
    WorkspaceQuickStartResponse,
    to_workspace_quick_start_response,
)
from app.api.schemas.workspace_readiness_schemas import (
    WorkspaceReadinessResponse,
    to_workspace_readiness_response,
)
from app.api.schemas.workspace_summary_schemas import (
    WorkspaceSummaryResponse,
    to_workspace_summary_response,
)
from app.core.domain.workspace_dashboard import WorkspaceDashboard


class WorkspaceDashboardResponse(BaseModel):
    workspace_id: str
    workspace_name: str
    assistant_mode: str
    status: str
    summary: WorkspaceSummaryResponse
    readiness: WorkspaceReadinessResponse
    quick_start: WorkspaceQuickStartResponse
    assistant_recommendation: WorkspaceAssistantRecommendationResponse
    recent_events: list[TimelineEventResponse]
    runtime_health: RuntimeHealthResponse
    primary_next_action_id: str | None
    primary_next_action_title: str | None
    models_summary: WorkspaceModelsDashboardSummaryResponse | None


def to_workspace_dashboard_response(
    dashboard: WorkspaceDashboard,
) -> WorkspaceDashboardResponse:
    return WorkspaceDashboardResponse(
        workspace_id=dashboard.workspace_id,
        workspace_name=dashboard.workspace_name,
        assistant_mode=dashboard.assistant_mode,
        status=dashboard.status,
        summary=to_workspace_summary_response(dashboard.summary),
        readiness=to_workspace_readiness_response(dashboard.readiness),
        quick_start=to_workspace_quick_start_response(dashboard.quick_start),
        assistant_recommendation=to_workspace_assistant_recommendation_response(
            dashboard.assistant_recommendation
        ),
        recent_events=[to_timeline_event_response(event) for event in dashboard.recent_events],
        runtime_health=to_runtime_health_response(dashboard.runtime_health),
        primary_next_action_id=dashboard.primary_next_action_id,
        primary_next_action_title=dashboard.primary_next_action_title,
        models_summary=(
            to_workspace_models_dashboard_summary_response(dashboard.models_summary)
            if dashboard.models_summary is not None
            else None
        ),
    )
