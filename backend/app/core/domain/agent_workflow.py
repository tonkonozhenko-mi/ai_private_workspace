from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


AGENT_STEP_STATUSES = {"todo", "in_progress", "done", "skipped", "needs_review"}


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
    notes: str | None = None
    updated_at: str | None = None


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
            updated_steps.append(replace(step, status=status, notes=notes, updated_at=now))
        else:
            updated_steps.append(step)
    if not found:
        raise KeyError(step_id)
    workflow_status = _workflow_status_from_steps(updated_steps)
    return replace(workflow, steps=updated_steps, status=workflow_status, updated_at=now)


def archive_agent_workflow(workflow: AgentWorkflowDraft, archived: bool) -> AgentWorkflowDraft:
    now = utc_now_iso()
    return replace(workflow, archived_at=now if archived else None, updated_at=now)


def _workflow_status_from_steps(steps: list[AgentWorkflowStep]) -> str:
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
