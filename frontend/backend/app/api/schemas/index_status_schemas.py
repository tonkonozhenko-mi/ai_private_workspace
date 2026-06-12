from pydantic import BaseModel

from app.core.domain.index_status import WorkspaceIndexStatus


class WorkspaceIndexStatusResponse(BaseModel):
    workspace_id: str
    status: str
    indexed_files_count: int
    chunks_count: int
    skipped_files_count: int
    last_indexed_at: str | None
    last_error: str | None


def to_workspace_index_status_response(
    status: WorkspaceIndexStatus,
) -> WorkspaceIndexStatusResponse:
    return WorkspaceIndexStatusResponse(
        workspace_id=status.workspace_id,
        status=status.status,
        indexed_files_count=status.indexed_files_count,
        chunks_count=status.chunks_count,
        skipped_files_count=status.skipped_files_count,
        last_indexed_at=status.last_indexed_at,
        last_error=status.last_error,
    )
