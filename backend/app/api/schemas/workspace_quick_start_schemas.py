from pydantic import BaseModel

from app.core.domain.workspace_quick_start import QuickStartStep, WorkspaceQuickStart


class QuickStartStepResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    action_id: str | None
    endpoint: str | None


class WorkspaceQuickStartResponse(BaseModel):
    workspace_id: str
    status: str
    next_action_id: str | None
    next_action_title: str | None
    steps: list[QuickStartStepResponse]
    notes: list[str]


def to_quick_start_step_response(step: QuickStartStep) -> QuickStartStepResponse:
    return QuickStartStepResponse(
        id=step.id,
        title=step.title,
        description=step.description,
        status=step.status,
        action_id=step.action_id,
        endpoint=step.endpoint,
    )


def to_workspace_quick_start_response(
    quick_start: WorkspaceQuickStart,
) -> WorkspaceQuickStartResponse:
    return WorkspaceQuickStartResponse(
        workspace_id=quick_start.workspace_id,
        status=quick_start.status,
        next_action_id=quick_start.next_action_id,
        next_action_title=quick_start.next_action_title,
        steps=[to_quick_start_step_response(step) for step in quick_start.steps],
        notes=quick_start.notes,
    )
