from pydantic import BaseModel

from app.core.domain.selected_embedding_indexing_plan import (
    SelectedEmbeddingIndexingPlan,
)


class SelectedEmbeddingIndexingPlanResponse(BaseModel):
    workspace_id: str
    selected_provider: str | None
    selected_model: str | None
    active_provider: str
    active_model: str
    index_status: str
    can_index_now: bool
    can_search_now: bool
    requires_backend_restart: bool
    requires_reindex: bool
    requires_new_vector_collection: bool
    plan_status: str
    recommended_actions: list[str]
    warnings: list[str]
    notes: list[str]


def to_selected_embedding_indexing_plan_response(
    plan: SelectedEmbeddingIndexingPlan,
) -> SelectedEmbeddingIndexingPlanResponse:
    return SelectedEmbeddingIndexingPlanResponse(
        workspace_id=plan.workspace_id,
        selected_provider=plan.selected_provider,
        selected_model=plan.selected_model,
        active_provider=plan.active_provider,
        active_model=plan.active_model,
        index_status=plan.index_status,
        can_index_now=plan.can_index_now,
        can_search_now=plan.can_search_now,
        requires_backend_restart=plan.requires_backend_restart,
        requires_reindex=plan.requires_reindex,
        requires_new_vector_collection=plan.requires_new_vector_collection,
        plan_status=plan.plan_status,
        recommended_actions=plan.recommended_actions,
        warnings=plan.warnings,
        notes=plan.notes,
    )
