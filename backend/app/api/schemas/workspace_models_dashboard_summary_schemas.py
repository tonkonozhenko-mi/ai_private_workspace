from pydantic import BaseModel

from app.core.domain.workspace_models_dashboard_summary import (
    WorkspaceModelsDashboardSummary,
)


class WorkspaceModelsDashboardSummaryResponse(BaseModel):
    workspace_id: str
    overall_status: str
    primary_next_action_id: str | None
    primary_next_action_title: str | None
    selected_llm: str | None
    selected_embedding: str | None
    active_llm: str
    active_embedding: str
    can_ask_with_selected_llm: bool
    can_search_with_selected_embedding: bool
    top_recommended_model: str | None
    top_recommended_model_score: int | None
    performance_models_count: int
    warnings_count: int
    notes: list[str]


def to_workspace_models_dashboard_summary_response(
    summary: WorkspaceModelsDashboardSummary,
) -> WorkspaceModelsDashboardSummaryResponse:
    return WorkspaceModelsDashboardSummaryResponse(
        workspace_id=summary.workspace_id,
        overall_status=summary.overall_status,
        primary_next_action_id=summary.primary_next_action_id,
        primary_next_action_title=summary.primary_next_action_title,
        selected_llm=summary.selected_llm,
        selected_embedding=summary.selected_embedding,
        active_llm=summary.active_llm,
        active_embedding=summary.active_embedding,
        can_ask_with_selected_llm=summary.can_ask_with_selected_llm,
        can_search_with_selected_embedding=summary.can_search_with_selected_embedding,
        top_recommended_model=summary.top_recommended_model,
        top_recommended_model_score=summary.top_recommended_model_score,
        performance_models_count=summary.performance_models_count,
        warnings_count=summary.warnings_count,
        notes=summary.notes,
    )
