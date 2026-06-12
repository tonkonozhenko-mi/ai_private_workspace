from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceCapability:
    id: str
    available: bool
    reason: str


@dataclass(frozen=True)
class WorkspaceReadiness:
    workspace_id: str
    status: str
    can_scan: bool
    can_analyze: bool
    can_index: bool
    can_ask: bool
    can_execute_commands: bool
    capabilities: list[WorkspaceCapability]
    recommended_next_steps: list[str]
    configuration: dict[str, str]
