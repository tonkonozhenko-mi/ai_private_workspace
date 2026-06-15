from pydantic import BaseModel

from app.core.domain.workspace_storage import WorkspaceStorageBreakdown


class WorkspaceStorageResponse(BaseModel):
    workspace_id: str
    total_bytes: int
    breakdown: dict[str, int]
    computed_at: str | None


def to_workspace_storage_response(
    breakdown: WorkspaceStorageBreakdown,
) -> WorkspaceStorageResponse:
    return WorkspaceStorageResponse(
        workspace_id=breakdown.workspace_id,
        total_bytes=breakdown.total_bytes,
        breakdown=dict(breakdown.categories),
        computed_at=breakdown.computed_at,
    )
