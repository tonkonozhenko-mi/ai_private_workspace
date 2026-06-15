from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkspaceOverviewItem:
    workspace_id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: str
    archived_at: str | None
    is_archived: bool
    persistence: str
    readiness_status: str
    quick_start_status: str
    next_action_id: str | None
    next_action_title: str | None
    has_scan: bool
    detected_skills_count: int
    index_status: str
    commands_pending_count: int
    last_event_title: str | None
    last_event_type: str | None
    last_event_at: str | None
    storage_total_bytes: int = 0
    storage_breakdown: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkspacesOverview:
    total_workspaces: int
    items: list[WorkspaceOverviewItem]
