from pydantic import BaseModel, Field

from app.core.domain.agent_workflow import (
    AgentStepApprovalPreview,
    AgentWorkflowDraft,
    AgentWorkflowExecutionReadiness,
    AgentWorkflowExecutionReadinessStep,
    AgentWorkflowStep,
)


class CreateAgentWorkflowRequest(BaseModel):
    goal: str = Field(..., min_length=3, max_length=2000)
    provider: str | None = None
    model: str | None = None


class UpdateAgentWorkflowStepRequest(BaseModel):
    status: str = Field(..., pattern="^(todo|in_progress|done|skipped|needs_review)$")
    notes: str | None = Field(default=None, max_length=2000)


class UpdateAgentWorkflowStepApprovalRequest(BaseModel):
    approval_status: str = Field(..., pattern="^(not_required|pending|approved|rejected|revoked)$")
    approval_note: str | None = Field(default=None, max_length=2000)


class UpdateAgentWorkflowStepEvidenceRequest(BaseModel):
    evidence_status: str = Field(..., pattern="^(not_provided|provided|needs_review|verified)$")
    evidence_summary: str | None = Field(default=None, max_length=2000)
    evidence_sources: list[str] = Field(default_factory=list)


class AgentWorkflowArchiveRequest(BaseModel):
    archived: bool = True


class AgentWorkflowStepApprovalPreviewResponse(BaseModel):
    workflow_id: str
    step_id: str
    title: str
    approval_status: str
    proposed_tool: str | None
    tool_risk: str
    allowed_execution: str
    requires_user_confirmation: bool
    execution_hint: str
    evidence_hint: str
    approval_checklist: list[str]
    blocked_actions: list[str]
    safety_note: str


class AgentWorkflowStepResponse(BaseModel):
    id: str
    order: int
    title: str
    description: str
    status: str
    allowed_execution: str
    verification: str
    requires_user_confirmation: bool
    approval_status: str
    approval_note: str | None
    proposed_tool: str | None
    tool_risk: str
    execution_hint: str | None
    evidence_hint: str | None
    approved_at: str | None
    evidence_status: str
    evidence_summary: str | None
    evidence_sources: list[str]
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
    approval_required_steps_count: int
    approved_steps_count: int
    pending_approval_steps_count: int
    approval_readiness: str
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


class AgentWorkflowExecutionReadinessStepResponse(BaseModel):
    step_id: str
    title: str
    proposed_tool: str | None
    tool_status: str
    tool_risk: str
    approval_status: str
    evidence_status: str
    ready_for_manual_execution: bool
    blockers: list[str]
    next_action: str


class AgentWorkflowExecutionReadinessResponse(BaseModel):
    workspace_id: str
    workflow_id: str
    status: str
    approved_tools_count: int
    risky_tools_count: int
    ready_steps_count: int
    blocked_steps_count: int
    steps: list[AgentWorkflowExecutionReadinessStepResponse]
    guardrails: list[str]
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
        approval_status=step.approval_status,
        approval_note=step.approval_note,
        proposed_tool=step.proposed_tool,
        tool_risk=step.tool_risk,
        execution_hint=step.execution_hint,
        evidence_hint=step.evidence_hint,
        approved_at=step.approved_at,
        evidence_status=step.evidence_status,
        evidence_summary=step.evidence_summary,
        evidence_sources=step.evidence_sources or [],
        notes=step.notes,
        updated_at=step.updated_at,
    )


def to_agent_step_approval_preview_response(
    preview: AgentStepApprovalPreview,
) -> AgentWorkflowStepApprovalPreviewResponse:
    return AgentWorkflowStepApprovalPreviewResponse(
        workflow_id=preview.workflow_id,
        step_id=preview.step_id,
        title=preview.title,
        approval_status=preview.approval_status,
        proposed_tool=preview.proposed_tool,
        tool_risk=preview.tool_risk,
        allowed_execution=preview.allowed_execution,
        requires_user_confirmation=preview.requires_user_confirmation,
        execution_hint=preview.execution_hint,
        evidence_hint=preview.evidence_hint,
        approval_checklist=preview.approval_checklist,
        blocked_actions=preview.blocked_actions,
        safety_note=preview.safety_note,
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
        approval_required_steps_count=workflow.approval_required_steps_count,
        approved_steps_count=workflow.approved_steps_count,
        pending_approval_steps_count=workflow.pending_approval_steps_count,
        approval_readiness=workflow.approval_readiness,
        guardrails=workflow.guardrails,
        unsupported_actions=workflow.unsupported_actions,
        safety_note=workflow.safety_note,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        archived_at=workflow.archived_at,
        is_archived=workflow.archived_at is not None,
    )


def to_agent_workflow_execution_readiness_step_response(
    step: AgentWorkflowExecutionReadinessStep,
) -> AgentWorkflowExecutionReadinessStepResponse:
    return AgentWorkflowExecutionReadinessStepResponse(**step.__dict__)


def to_agent_workflow_execution_readiness_response(
    readiness: AgentWorkflowExecutionReadiness,
) -> AgentWorkflowExecutionReadinessResponse:
    return AgentWorkflowExecutionReadinessResponse(
        workspace_id=readiness.workspace_id,
        workflow_id=readiness.workflow_id,
        status=readiness.status,
        approved_tools_count=readiness.approved_tools_count,
        risky_tools_count=readiness.risky_tools_count,
        ready_steps_count=readiness.ready_steps_count,
        blocked_steps_count=readiness.blocked_steps_count,
        steps=[
            to_agent_workflow_execution_readiness_step_response(step) for step in readiness.steps
        ],
        guardrails=readiness.guardrails,
        safety_note=readiness.safety_note,
    )
