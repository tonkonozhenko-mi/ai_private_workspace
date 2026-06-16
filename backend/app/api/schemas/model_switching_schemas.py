from pydantic import BaseModel, Field

from app.core.domain.model_switching import ModelSwitchImpact, ModelSwitchingPlan


class CreateModelSwitchingPlanRequest(BaseModel):
    model_type: str = Field(..., min_length=1)
    current_provider: str = Field(..., min_length=1)
    current_model: str = Field(..., min_length=1)
    target_provider: str = Field(..., min_length=1)
    target_model: str = Field(..., min_length=1)
    workspace_id: str | None = None


class ModelSwitchImpactResponse(BaseModel):
    area: str
    impact: str
    requires_reindex: bool
    requires_backend_restart: bool
    risk: str
    explanation: str


class ModelSwitchingPlanResponse(BaseModel):
    workspace_id: str | None
    model_type: str
    current_provider: str
    current_model: str
    target_provider: str
    target_model: str
    requires_reindex: bool
    requires_new_vector_collection: bool
    can_switch_without_reindex: bool
    requires_backend_restart: bool
    recommended_actions: list[str]
    impacts: list[ModelSwitchImpactResponse]
    notes: list[str]


def to_model_switch_impact_response(
    impact: ModelSwitchImpact,
) -> ModelSwitchImpactResponse:
    return ModelSwitchImpactResponse(
        area=impact.area,
        impact=impact.impact,
        requires_reindex=impact.requires_reindex,
        requires_backend_restart=impact.requires_backend_restart,
        risk=impact.risk,
        explanation=impact.explanation,
    )


def to_model_switching_plan_response(
    plan: ModelSwitchingPlan,
) -> ModelSwitchingPlanResponse:
    return ModelSwitchingPlanResponse(
        workspace_id=plan.workspace_id,
        model_type=plan.model_type,
        current_provider=plan.current_provider,
        current_model=plan.current_model,
        target_provider=plan.target_provider,
        target_model=plan.target_model,
        requires_reindex=plan.requires_reindex,
        requires_new_vector_collection=plan.requires_new_vector_collection,
        can_switch_without_reindex=plan.can_switch_without_reindex,
        requires_backend_restart=plan.requires_backend_restart,
        recommended_actions=plan.recommended_actions,
        impacts=[to_model_switch_impact_response(impact) for impact in plan.impacts],
        notes=plan.notes,
    )
