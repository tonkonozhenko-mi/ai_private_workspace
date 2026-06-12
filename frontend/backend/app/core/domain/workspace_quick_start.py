from dataclasses import dataclass


@dataclass(frozen=True)
class QuickStartStep:
    id: str
    title: str
    description: str
    status: str
    action_id: str | None
    endpoint: str | None


@dataclass(frozen=True)
class WorkspaceQuickStart:
    workspace_id: str
    status: str
    next_action_id: str | None
    next_action_title: str | None
    steps: list[QuickStartStep]
    notes: list[str]
