from pydantic import BaseModel, Field

from app.core.domain.workspace_file import WorkspaceFileWriteResult


class WriteWorkspaceFileRequest(BaseModel):
    relative_path: str = Field(..., min_length=1)
    content: str
    overwrite: bool = False


class WorkspaceFileWriteResponse(BaseModel):
    workspace_id: str
    relative_path: str
    bytes_written: int
    replaced_existing: bool
    status: str


def to_workspace_file_write_response(
    result: WorkspaceFileWriteResult,
) -> WorkspaceFileWriteResponse:
    return WorkspaceFileWriteResponse(
        workspace_id=result.workspace_id,
        relative_path=result.relative_path,
        bytes_written=result.bytes_written,
        replaced_existing=result.replaced_existing,
        status=result.status,
    )
