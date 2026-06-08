from pydantic import BaseModel

from app.api.schemas.model_performance_schemas import (
    ModelPerformanceSummaryResponse,
    to_model_performance_summary_response,
)
from app.api.schemas.selected_embedding_indexing_plan_schemas import (
    SelectedEmbeddingIndexingPlanResponse,
    to_selected_embedding_indexing_plan_response,
)
from app.api.schemas.selected_model_usage_plan_schemas import (
    SelectedModelUsagePlanResponse,
    to_selected_model_usage_plan_response,
)
from app.api.schemas.workspace_model_recommendation_schemas import (
    WorkspaceModelRecommendationResultResponse,
    to_workspace_model_recommendation_result_response,
)
from app.api.schemas.workspace_model_selection_schemas import (
    WorkspaceModelSelectionResponse,
    to_workspace_model_selection_response,
)
from app.api.schemas.workspace_model_selection_status_schemas import (
    WorkspaceModelSelectionStatusResponse,
    to_workspace_model_selection_status_response,
)
from app.core.domain.workspace_models_dashboard import WorkspaceModelsDashboard


class WorkspaceModelsDashboardResponse(BaseModel):
    workspace_id: str
    selected_llm_provider: str | None
    selected_llm_model: str | None
    selected_embedding_provider: str | None
    selected_embedding_model: str | None
    overall_status: str
    primary_next_action_id: str | None
    primary_next_action_title: str | None
    selection: WorkspaceModelSelectionResponse
    selection_status: WorkspaceModelSelectionStatusResponse
    usage_plan: SelectedModelUsagePlanResponse
    embedding_indexing_plan: SelectedEmbeddingIndexingPlanResponse
    recommendations: WorkspaceModelRecommendationResultResponse
    performance_summary: ModelPerformanceSummaryResponse
    notes: list[str]


def to_workspace_models_dashboard_response(
    dashboard: WorkspaceModelsDashboard,
) -> WorkspaceModelsDashboardResponse:
    return WorkspaceModelsDashboardResponse(
        workspace_id=dashboard.workspace_id,
        selected_llm_provider=dashboard.selected_llm_provider,
        selected_llm_model=dashboard.selected_llm_model,
        selected_embedding_provider=dashboard.selected_embedding_provider,
        selected_embedding_model=dashboard.selected_embedding_model,
        overall_status=dashboard.overall_status,
        primary_next_action_id=dashboard.primary_next_action_id,
        primary_next_action_title=dashboard.primary_next_action_title,
        selection=to_workspace_model_selection_response(dashboard.selection),
        selection_status=to_workspace_model_selection_status_response(
            dashboard.selection_status
        ),
        usage_plan=to_selected_model_usage_plan_response(dashboard.usage_plan),
        embedding_indexing_plan=to_selected_embedding_indexing_plan_response(
            dashboard.embedding_indexing_plan
        ),
        recommendations=to_workspace_model_recommendation_result_response(
            dashboard.recommendations
        ),
        performance_summary=to_model_performance_summary_response(
            dashboard.performance_summary
        ),
        notes=dashboard.notes,
    )
