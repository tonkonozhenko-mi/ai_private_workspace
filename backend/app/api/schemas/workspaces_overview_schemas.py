from pydantic import BaseModel

from app.core.domain.workspaces_overview import WorkspaceOverviewItem, WorkspacesOverview


class WorkspaceOverviewItemResponse(BaseModel):
    workspace_id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: str
    archived_at: str | None
    is_archived: bool
    persistence: str = "saved"
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
    storage_breakdown: dict[str, int] = {}


class WorkspacesOverviewResponse(BaseModel):
    total_workspaces: int
    items: list[WorkspaceOverviewItemResponse]


def to_workspace_overview_item_response(
    item: WorkspaceOverviewItem,
) -> WorkspaceOverviewItemResponse:
    return WorkspaceOverviewItemResponse(
        workspace_id=item.workspace_id,
        name=item.name,
        project_path=item.project_path,
        assistant_mode=item.assistant_mode,
        privacy_mode=item.privacy_mode,
        created_at=item.created_at,
        archived_at=item.archived_at,
        is_archived=item.is_archived,
        persistence=item.persistence,
        readiness_status=item.readiness_status,
        quick_start_status=item.quick_start_status,
        next_action_id=item.next_action_id,
        next_action_title=item.next_action_title,
        has_scan=item.has_scan,
        detected_skills_count=item.detected_skills_count,
        index_status=item.index_status,
        commands_pending_count=item.commands_pending_count,
        last_event_title=item.last_event_title,
        last_event_type=item.last_event_type,
        last_event_at=item.last_event_at,
        storage_total_bytes=item.storage_total_bytes,
        storage_breakdown=dict(item.storage_breakdown),
    )


def to_workspaces_overview_response(
    overview: WorkspacesOverview,
) -> WorkspacesOverviewResponse:
    return WorkspacesOverviewResponse(
        total_workspaces=overview.total_workspaces,
        items=[
            to_workspace_overview_item_response(item) for item in overview.items
        ],
    )
