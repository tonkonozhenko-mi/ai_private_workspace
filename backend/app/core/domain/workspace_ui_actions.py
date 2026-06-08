from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceUIAction:
    id: str
    title: str
    description: str
    method: str
    endpoint: str
    category: str
    status: str
    is_primary: bool
    mutates_data: bool
    reason: str


@dataclass(frozen=True)
class WorkspaceUIActionCatalog:
    workspace_id: str
    primary_action_id: str | None
    actions: list[WorkspaceUIAction]
    notes: list[str]
