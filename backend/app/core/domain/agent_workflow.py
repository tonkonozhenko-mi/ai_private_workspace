from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


AGENT_STEP_STATUSES = {"todo", "in_progress", "done", "skipped", "needs_review"}
AGENT_APPROVAL_STATUSES = {"not_required", "pending", "approved", "rejected", "revoked"}


@dataclass(frozen=True)
class AgentWorkflowStep:
    id: str
    order: int
    title: str
    description: str
    status: str
    allowed_execution: str
    verification: str
    requires_user_confirmation: bool
    approval_status: str = "pending"
    approval_note: str | None = None
    proposed_tool: str | None = None
    tool_risk: str = "manual_review"
    execution_hint: str | None = None
    evidence_hint: str | None = None
    approved_at: str | None = None
    notes: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class AgentStepApprovalPreview:
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


@dataclass(frozen=True)
class AgentWorkflowDraft:
    id: str
    workspace_id: str
    title: str
    goal: str
    provider: str | None
    model: str | None
    readiness: str
    agent_mode: str
    status: str
    steps: list[AgentWorkflowStep]
    guardrails: list[str]
    unsupported_actions: list[str]
    safety_note: str
    created_at: str
    updated_at: str
    archived_at: str | None = None

    @property
    def completed_steps_count(self) -> int:
        return len([step for step in self.steps if step.status == "done"])

    @property
    def total_steps_count(self) -> int:
        return len(self.steps)

    @property
    def progress_percent(self) -> int:
        if not self.steps:
            return 0
        return round((self.completed_steps_count / len(self.steps)) * 100)

    @property
    def approval_required_steps_count(self) -> int:
        return len([step for step in self.steps if step.requires_user_confirmation])

    @property
    def approved_steps_count(self) -> int:
        return len([step for step in self.steps if step.approval_status == "approved"])

    @property
    def pending_approval_steps_count(self) -> int:
        return len([step for step in self.steps if step.approval_status == "pending"])

    @property
    def approval_readiness(self) -> str:
        if not self.steps:
            return "no_steps"
        if any(step.approval_status == "rejected" for step in self.steps):
            return "blocked"
        if self.pending_approval_steps_count:
            return "approval_required"
        return "ready_for_manual_tracking"


def create_agent_workflow_from_preview(*, workspace_id: str, goal: str, provider: str | None, model: str | None, readiness: str, agent_mode: str, preview_steps: list, guardrails: list[str], unsupported_actions: list[str], safety_note: str) -> AgentWorkflowDraft:
    now = utc_now_iso()
    steps = [
        AgentWorkflowStep(
            id=str(uuid4()),
            order=step.order,
            title=step.title,
            description=step.description,
            status="todo",
            allowed_execution=step.allowed_execution,
            verification=step.verification,
            requires_user_confirmation=step.requires_user_confirmation,
            approval_status="pending" if step.requires_user_confirmation else "not_required",
            proposed_tool=_proposed_tool_for_step(step.allowed_execution, step.title),
            tool_risk=_tool_risk_for_step(step.allowed_execution),
            execution_hint=_execution_hint_for_step(step.allowed_execution),
            evidence_hint=step.verification,
            updated_at=now,
        )
        for step in preview_steps
    ]
    return AgentWorkflowDraft(
        id=str(uuid4()),
        workspace_id=workspace_id,
        title=_title_from_goal(goal),
        goal=goal.strip(),
        provider=provider,
        model=model,
        readiness=readiness,
        agent_mode=agent_mode,
        status="draft",
        steps=steps,
        guardrails=guardrails,
        unsupported_actions=unsupported_actions,
        safety_note=safety_note,
        created_at=now,
        updated_at=now,
    )


def update_workflow_step_status(workflow: AgentWorkflowDraft, step_id: str, status: str, notes: str | None = None) -> AgentWorkflowDraft:
    if status not in AGENT_STEP_STATUSES:
        raise ValueError(f"Unsupported agent step status: {status}")
    now = utc_now_iso()
    updated_steps = []
    found = False
    for step in workflow.steps:
        if step.id == step_id:
            found = True
            if status in {"in_progress", "done"} and step.requires_user_confirmation and step.approval_status != "approved":
                raise ValueError("Step must be approved before marking it in progress or done.")
            updated_steps.append(replace(step, status=status, notes=notes, updated_at=now))
        else:
            updated_steps.append(step)
    if not found:
        raise KeyError(step_id)
    workflow_status = _workflow_status_from_steps(updated_steps)
    return replace(workflow, steps=updated_steps, status=workflow_status, updated_at=now)


def update_workflow_step_approval(workflow: AgentWorkflowDraft, step_id: str, approval_status: str, approval_note: str | None = None) -> AgentWorkflowDraft:
    if approval_status not in AGENT_APPROVAL_STATUSES:
        raise ValueError(f"Unsupported agent approval status: {approval_status}")
    now = utc_now_iso()
    updated_steps = []
    found = False
    for step in workflow.steps:
        if step.id == step_id:
            found = True
            if not step.requires_user_confirmation and approval_status not in {"not_required", "approved"}:
                raise ValueError("This step does not require an approval gate.")
            updated_steps.append(
                replace(
                    step,
                    approval_status=approval_status,
                    approval_note=approval_note,
                    approved_at=now if approval_status == "approved" else None,
                    updated_at=now,
                )
            )
        else:
            updated_steps.append(step)
    if not found:
        raise KeyError(step_id)
    workflow_status = _workflow_status_from_steps(updated_steps)
    return replace(workflow, steps=updated_steps, status=workflow_status, updated_at=now)


def build_step_approval_preview(workflow: AgentWorkflowDraft, step_id: str) -> AgentStepApprovalPreview:
    step = next((item for item in workflow.steps if item.id == step_id), None)
    if step is None:
        raise KeyError(step_id)
    return AgentStepApprovalPreview(
        workflow_id=workflow.id,
        step_id=step.id,
        title=step.title,
        approval_status=step.approval_status,
        proposed_tool=step.proposed_tool,
        tool_risk=step.tool_risk,
        allowed_execution=step.allowed_execution,
        requires_user_confirmation=step.requires_user_confirmation,
        execution_hint=step.execution_hint or _execution_hint_for_step(step.allowed_execution),
        evidence_hint=step.evidence_hint or step.verification,
        approval_checklist=[
            "Review the step goal and expected evidence.",
            "Confirm the tool is approved for this workspace.",
            "Run any command manually in your terminal, not from the browser UI.",
            "Paste notes or evidence back into the workflow after checking the result.",
        ],
        blocked_actions=[
            "Automatic shell execution",
            "Automatic file modification",
            "Automatic git commit/push",
            "Automatic scan/index/rebuild/restart",
        ],
        safety_note="Approval records user intent only. It does not execute tools, commands, file edits, or MCP calls.",
    )


def archive_agent_workflow(workflow: AgentWorkflowDraft, archived: bool) -> AgentWorkflowDraft:
    now = utc_now_iso()
    return replace(workflow, archived_at=now if archived else None, updated_at=now)


def _workflow_status_from_steps(steps: list[AgentWorkflowStep]) -> str:
    if any(step.approval_status == "rejected" for step in steps):
        return "needs_review"
    if any(step.status == "needs_review" for step in steps):
        return "needs_review"
    if any(step.status == "in_progress" for step in steps):
        return "in_progress"
    actionable = [step for step in steps if step.status != "skipped"]
    if actionable and all(step.status == "done" for step in actionable):
        return "completed"
    return "draft"


def _title_from_goal(goal: str) -> str:
    value = " ".join(goal.strip().split())
    if not value:
        return "Agent workflow draft"
    return value[:80]


def _proposed_tool_for_step(allowed_execution: str, title: str) -> str | None:
    value = f"{allowed_execution} {title}".lower()
    if "shell" in value or "command" in value or "test" in value:
        return "shell.propose_command"
    if "git" in value:
        return "git.read"
    if "file" in value or "source" in value or "context" in value:
        return "filesystem.read"
    if "qdrant" in value or "search" in value:
        return "qdrant.search"
    return None


def _tool_risk_for_step(allowed_execution: str) -> str:
    value = allowed_execution.lower()
    if "write" in value or "shell" in value or "command" in value:
        return "manual_write_or_command"
    if "read" in value:
        return "read_only"
    return "manual_review"


def _execution_hint_for_step(allowed_execution: str) -> str:
    value = allowed_execution.lower()
    if "write" in value or "shell" in value or "command" in value:
        return "Prepare the command or patch, review it, then run it manually outside the browser UI only after approval."
    if "read" in value:
        return "Use approved read-only tools or retrieved sources to collect evidence before continuing."
    return "Treat this step as a manual checkpoint. Review the evidence and confirm before moving forward."
