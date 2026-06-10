from pydantic import BaseModel, Field

from app.core.domain.agent_workflow import AgentWorkflowDraft, AgentWorkflowStep


class CreateAgentWorkflowRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=2000)
    provider: str | None = None
    model: str | None = None


class UpdateAgentWorkflowStepRequest(BaseModel):
    status: str = Field(..., pattern="^(todo|in_progress|done|skipped|needs_review)$")
    notes: str | None = Field(default=None, max_length=2000)


class AgentWorkflowArchiveRequest(BaseModel):
    archived: bool = True


class AgentWorkflowStepResponse(BaseModel):
    id: str
    order: int
    title: str
    description: str
    status: str
    allowed_execution: str
    verification: str
    requires_user_confirmation: bool
    notes: str | None
    updated_at: str | None


class AgentWorkflowResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    goal: str
    provider: str | None
    model: str | None
    readiness: str
    agent_mode: str
    status: str
    steps: list[AgentWorkflowStepResponse]
    completed_steps_count: int
    total_steps_count: int
    progress_percent: int
    guardrails: list[str]
    unsupported_actions: list[str]
    safety_note: str
    created_at: str
    updated_at: str
    archived_at: str | None
    is_archived: bool


class AgentWorkflowListResponse(BaseModel):
    workspace_id: str
    items: list[AgentWorkflowResponse]
    safety_note: str


def to_agent_workflow_step_response(step: AgentWorkflowStep) -> AgentWorkflowStepResponse:
    return AgentWorkflowStepResponse(
        id=step.id,
        order=step.order,
        title=step.title,
        description=step.description,
        status=step.status,
        allowed_execution=step.allowed_execution,
        verification=step.verification,
        requires_user_confirmation=step.requires_user_confirmation,
        notes=step.notes,
        updated_at=step.updated_at,
    )


def to_agent_workflow_response(workflow: AgentWorkflowDraft) -> AgentWorkflowResponse:
    return AgentWorkflowResponse(
        id=workflow.id,
        workspace_id=workflow.workspace_id,
        title=workflow.title,
        goal=workflow.goal,
        provider=workflow.provider,
        model=workflow.model,
        readiness=workflow.readiness,
        agent_mode=workflow.agent_mode,
        status=workflow.status,
        steps=[to_agent_workflow_step_response(step) for step in workflow.steps],
        completed_steps_count=workflow.completed_steps_count,
        total_steps_count=workflow.total_steps_count,
        progress_percent=workflow.progress_percent,
        guardrails=workflow.guardrails,
        unsupported_actions=workflow.unsupported_actions,
        safety_note=workflow.safety_note,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        archived_at=workflow.archived_at,
        is_archived=workflow.archived_at is not None,
    )
