from pydantic import BaseModel


class WorkspaceJobResponse(BaseModel):
    job_id: str
    workspace_id: str
    job_type: str
    status: str
    title: str
    message: str | None = None
    result_summary: dict[str, str] = {}
    request_summary: dict[str, str] = {}
    error: str | None = None
    cancellation_requested: bool = False
    progress_current: int | None = None
    progress_total: int | None = None
    progress_percent: float | None = None
    current_step: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
