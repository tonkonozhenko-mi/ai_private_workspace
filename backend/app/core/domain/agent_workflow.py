from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


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
    evidence_status: str = "not_provided"
    evidence_summary: str | None = None
    evidence_sources: list[str] | None = None
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


@dataclass(frozen=True)
class AgentWorkflowExecutionReadinessStep:
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


@dataclass(frozen=True)
class AgentWorkflowExecutionReadiness:
    workspace_id: str
    workflow_id: str
    status: str
    approved_tools_count: int
    risky_tools_count: int
    ready_steps_count: int
    blocked_steps_count: int
    steps: list[AgentWorkflowExecutionReadinessStep]
    guardrails: list[str]
    safety_note: str


def create_agent_workflow_from_preview(
    *,
    workspace_id: str,
    goal: str,
    provider: str | None,
    model: str | None,
    readiness: str,
    agent_mode: str,
    preview_steps: list,
    guardrails: list[str],
    unsupported_actions: list[str],
    safety_note: str,
) -> AgentWorkflowDraft:
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


def update_workflow_step_status(
    workflow: AgentWorkflowDraft, step_id: str, status: str, notes: str | None = None
) -> AgentWorkflowDraft:
    if status not in AGENT_STEP_STATUSES:
        raise ValueError(f"Unsupported agent step status: {status}")
    now = utc_now_iso()
    updated_steps = []
    found = False
    for step in workflow.steps:
        if step.id == step_id:
            found = True
            if (
                status in {"in_progress", "done"}
                and step.requires_user_confirmation
                and step.approval_status != "approved"
            ):
                raise ValueError("Step must be approved before marking it in progress or done.")
            updated_steps.append(replace(step, status=status, notes=notes, updated_at=now))
        else:
            updated_steps.append(step)
    if not found:
        raise KeyError(step_id)
    workflow_status = _workflow_status_from_steps(updated_steps)
    return replace(workflow, steps=updated_steps, status=workflow_status, updated_at=now)


def update_workflow_step_approval(
    workflow: AgentWorkflowDraft,
    step_id: str,
    approval_status: str,
    approval_note: str | None = None,
) -> AgentWorkflowDraft:
    if approval_status not in AGENT_APPROVAL_STATUSES:
        raise ValueError(f"Unsupported agent approval status: {approval_status}")
    now = utc_now_iso()
    updated_steps = []
    found = False
    for step in workflow.steps:
        if step.id == step_id:
            found = True
            if not step.requires_user_confirmation and approval_status not in {
                "not_required",
                "approved",
            }:
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


def update_workflow_step_evidence(
    workflow: AgentWorkflowDraft,
    step_id: str,
    evidence_status: str,
    evidence_summary: str | None = None,
    evidence_sources: list[str] | None = None,
) -> AgentWorkflowDraft:
    if evidence_status not in {"not_provided", "provided", "needs_review", "verified"}:
        raise ValueError(f"Unsupported evidence status: {evidence_status}")
    now = utc_now_iso()
    updated_steps = []
    found = False
    for step in workflow.steps:
        if step.id == step_id:
            found = True
            updated_steps.append(
                replace(
                    step,
                    evidence_status=evidence_status,
                    evidence_summary=evidence_summary,
                    evidence_sources=evidence_sources or [],
                    updated_at=now,
                )
            )
        else:
            updated_steps.append(step)
    if not found:
        raise KeyError(step_id)
    return replace(workflow, steps=updated_steps, updated_at=now)


def build_workflow_execution_readiness(
    workflow: AgentWorkflowDraft, approved_tools: list[dict[str, str]]
) -> AgentWorkflowExecutionReadiness:
    approved_tool_names = {
        tool.get("tool", "")
        for tool in approved_tools
        if tool.get("status") == "approved" and tool.get("enabled") == "true"
    }
    risky_tool_names = {
        tool.get("tool", "")
        for tool in approved_tools
        if tool.get("status") == "approved" and tool.get("risk_level") != "read_only"
    }
    readiness_steps: list[AgentWorkflowExecutionReadinessStep] = []
    for step in workflow.steps:
        blockers: list[str] = []
        proposed_tool = step.proposed_tool
        tool_status = "manual_checkpoint"
        if proposed_tool:
            tool_status = "approved" if proposed_tool in approved_tool_names else "not_approved"
        if step.requires_user_confirmation and step.approval_status != "approved":
            blockers.append("Step approval is required.")
        if proposed_tool and proposed_tool not in approved_tool_names:
            blockers.append("Proposed MCP/tool is not approved for this workspace.")
        if step.tool_risk != "read_only" and step.approval_status != "approved":
            blockers.append(
                "Risky or manual tool requires explicit approval before tracking execution."
            )
        ready = not blockers
        if ready and step.evidence_status in {"provided", "verified"}:
            next_action = "Review evidence and mark the step done if the result is correct."
        elif ready:
            next_action = "Run/check manually outside the browser, then attach evidence."
        else:
            next_action = "Resolve blockers before manual execution tracking."
        readiness_steps.append(
            AgentWorkflowExecutionReadinessStep(
                step_id=step.id,
                title=step.title,
                proposed_tool=proposed_tool,
                tool_status=tool_status,
                tool_risk=step.tool_risk,
                approval_status=step.approval_status,
                evidence_status=step.evidence_status,
                ready_for_manual_execution=ready,
                blockers=blockers,
                next_action=next_action,
            )
        )
    ready_count = len([step for step in readiness_steps if step.ready_for_manual_execution])
    blocked_count = len(readiness_steps) - ready_count
    if blocked_count:
        status = "blocked"
    elif ready_count:
        status = "ready_for_manual_execution"
    else:
        status = "no_steps"
    return AgentWorkflowExecutionReadiness(
        workspace_id=workflow.workspace_id,
        workflow_id=workflow.id,
        status=status,
        approved_tools_count=len(approved_tool_names),
        risky_tools_count=len(risky_tool_names),
        ready_steps_count=ready_count,
        blocked_steps_count=blocked_count,
        steps=readiness_steps,
        guardrails=[
            "Execution readiness is advisory only.",
            "The browser UI never executes shell commands or MCP tools.",
            "Run commands manually or through a future backend sandbox with explicit approval.",
            "Attach evidence before marking risky steps done.",
        ],
        safety_note="This readiness panel maps approved tools to workflow steps. It does not execute tools, commands, file edits, git actions, scans, indexes, rebuilds, or restarts.",
    )


def build_step_approval_preview(
    workflow: AgentWorkflowDraft, step_id: str
) -> AgentStepApprovalPreview:
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
