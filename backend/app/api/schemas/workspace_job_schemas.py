from pydantic import BaseModel


class WorkspaceJobResponse(BaseModel):
    job_id: str
    workspace_id: str
    job_type: str
    status: str
    title: str
    message: str | None = None
    result_summary: dict[str, str] = {}
    error: str | None = None
    cancellation_requested: bool = False
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
