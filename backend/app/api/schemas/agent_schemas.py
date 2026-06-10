from pydantic import BaseModel, Field

from app.core.domain.agent_capability import (
    AgentCapability,
    AgentCapabilityCatalog,
    AgentPlanningPreview,
    AgentPlanStep,
)


class AgentCapabilityResponse(BaseModel):
    provider: str
    model: str
    display_name: str
    model_type: str
    readiness: str
    planning_supported: bool
    tool_calling_supported: bool
    json_mode_supported: bool
    safe_execution_supported: bool
    supported_agent_modes: list[str]
    recommended_use: str
    guardrails: list[str]
    evidence: list[str]
    limitations: list[str]


class AgentCapabilityCatalogResponse(BaseModel):
    summary: str
    models: list[AgentCapabilityResponse]
    recommended_models: list[str]
    safety_note: str
    planning_modes: list[str]


class AgentPlanningPreviewRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=2000)
    provider: str | None = None
    model: str | None = None


class AgentPlanStepResponse(BaseModel):
    order: int
    title: str
    description: str
    requires_user_confirmation: bool
    allowed_execution: str
    verification: str


class AgentPlanningPreviewResponse(BaseModel):
    goal: str
    selected_provider: str | None
    selected_model: str | None
    readiness: str
    agent_mode: str
    steps: list[AgentPlanStepResponse]
    unsupported_actions: list[str]
    guardrails: list[str]
    safety_note: str


def to_agent_capability_response(capability: AgentCapability) -> AgentCapabilityResponse:
    return AgentCapabilityResponse(
        provider=capability.provider,
        model=capability.model,
        display_name=capability.display_name,
        model_type=capability.model_type,
        readiness=capability.readiness,
        planning_supported=capability.planning_supported,
        tool_calling_supported=capability.tool_calling_supported,
        json_mode_supported=capability.json_mode_supported,
        safe_execution_supported=capability.safe_execution_supported,
        supported_agent_modes=capability.supported_agent_modes,
        recommended_use=capability.recommended_use,
        guardrails=capability.guardrails,
        evidence=capability.evidence,
        limitations=capability.limitations,
    )


def to_agent_capability_catalog_response(
    catalog: AgentCapabilityCatalog,
) -> AgentCapabilityCatalogResponse:
    return AgentCapabilityCatalogResponse(
        summary=catalog.summary,
        models=[to_agent_capability_response(model) for model in catalog.models],
        recommended_models=catalog.recommended_models,
        safety_note=catalog.safety_note,
        planning_modes=catalog.planning_modes,
    )


def to_agent_plan_step_response(step: AgentPlanStep) -> AgentPlanStepResponse:
    return AgentPlanStepResponse(
        order=step.order,
        title=step.title,
        description=step.description,
        requires_user_confirmation=step.requires_user_confirmation,
        allowed_execution=step.allowed_execution,
        verification=step.verification,
    )


def to_agent_planning_preview_response(
    preview: AgentPlanningPreview,
) -> AgentPlanningPreviewResponse:
    return AgentPlanningPreviewResponse(
        goal=preview.goal,
        selected_provider=preview.selected_provider,
        selected_model=preview.selected_model,
        readiness=preview.readiness,
        agent_mode=preview.agent_mode,
        steps=[to_agent_plan_step_response(step) for step in preview.steps],
        unsupported_actions=preview.unsupported_actions,
        guardrails=preview.guardrails,
        safety_note=preview.safety_note,
    )
