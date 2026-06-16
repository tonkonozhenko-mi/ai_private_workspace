from pydantic import BaseModel

from app.core.domain.local_ai_activation_guide import (
    LocalAIActivationGuide,
    LocalAIActivationStep,
)


class LocalAIActivationStepResponse(BaseModel):
    id: str
    title: str
    description: str
    command: str | None
    status: str
    reason: str
    category: str
    commands: list[str] | None = None


class LocalAIActivationGuideResponse(BaseModel):
    workspace_id: str
    overall_status: str
    selected_llm: str | None
    selected_embedding: str | None
    active_llm: str
    active_embedding: str
    selected_vector_store: str | None
    active_vector_store: str
    steps: list[LocalAIActivationStepResponse]
    notes: list[str]


def to_local_ai_activation_step_response(
    step: LocalAIActivationStep,
) -> LocalAIActivationStepResponse:
    return LocalAIActivationStepResponse(
        id=step.id,
        title=step.title,
        description=step.description,
        command=step.command,
        status=step.status,
        reason=step.reason,
        category=step.category,
        commands=step.commands,
    )


def to_local_ai_activation_guide_response(
    guide: LocalAIActivationGuide,
) -> LocalAIActivationGuideResponse:
    return LocalAIActivationGuideResponse(
        workspace_id=guide.workspace_id,
        overall_status=guide.overall_status,
        selected_llm=guide.selected_llm,
        selected_embedding=guide.selected_embedding,
        active_llm=guide.active_llm,
        active_embedding=guide.active_embedding,
        selected_vector_store=guide.selected_vector_store,
        active_vector_store=guide.active_vector_store,
        steps=[to_local_ai_activation_step_response(step) for step in guide.steps],
        notes=guide.notes,
    )
