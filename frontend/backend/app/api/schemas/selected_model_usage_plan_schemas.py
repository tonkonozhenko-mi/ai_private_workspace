from pydantic import BaseModel

from app.core.domain.selected_model_usage_plan import SelectedModelUsagePlan


class SelectedModelUsageCapabilityResponse(BaseModel):
    id: str
    available: bool
    status: str
    reason: str


class SelectedModelUsagePlanResponse(BaseModel):
    workspace_id: str
    can_ask_with_selected_llm: bool
    can_index_with_selected_embedding: bool
    can_search_with_selected_embedding: bool
    can_use_selected_models_fully: bool
    selected_llm_provider: str | None
    selected_llm_model: str | None
    selected_embedding_provider: str | None
    selected_embedding_model: str | None
    active_llm_provider: str
    active_llm_model: str
    active_embedding_provider: str
    active_embedding_model: str
    index_status: str
    capabilities: list[SelectedModelUsageCapabilityResponse]
    recommended_actions: list[str]
    notes: list[str]


def to_selected_model_usage_plan_response(
    plan: SelectedModelUsagePlan,
) -> SelectedModelUsagePlanResponse:
    return SelectedModelUsagePlanResponse(
        workspace_id=plan.workspace_id,
        can_ask_with_selected_llm=plan.can_ask_with_selected_llm,
        can_index_with_selected_embedding=plan.can_index_with_selected_embedding,
        can_search_with_selected_embedding=plan.can_search_with_selected_embedding,
        can_use_selected_models_fully=plan.can_use_selected_models_fully,
        selected_llm_provider=plan.selected_llm_provider,
        selected_llm_model=plan.selected_llm_model,
        selected_embedding_provider=plan.selected_embedding_provider,
        selected_embedding_model=plan.selected_embedding_model,
        active_llm_provider=plan.active_llm_provider,
        active_llm_model=plan.active_llm_model,
        active_embedding_provider=plan.active_embedding_provider,
        active_embedding_model=plan.active_embedding_model,
        index_status=plan.index_status,
        capabilities=[
            SelectedModelUsageCapabilityResponse(
                id=capability.id,
                available=capability.available,
                status=capability.status,
                reason=capability.reason,
            )
            for capability in plan.capabilities
        ],
        recommended_actions=plan.recommended_actions,
        notes=plan.notes,
    )
