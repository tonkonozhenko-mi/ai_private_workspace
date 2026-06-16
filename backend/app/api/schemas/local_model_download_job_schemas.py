from pydantic import BaseModel

from app.api.schemas.command_schemas import CommandProposalResponse, to_command_proposal_response
from app.core.domain.local_model_download_job import LocalModelDownloadJob


class LocalModelDownloadJobResponse(BaseModel):
    id: str
    command_id: str
    workspace_id: str
    provider: str
    model: str
    display_name: str
    status: str
    progress_percent: int
    progress_message: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    command_proposal: CommandProposalResponse
    stdout_preview: str | None
    stderr_preview: str | None
    exit_code: int | None
    cancel_requested_at: str | None
    cancellable: bool
    cancellation_summary: str
    safety_summary: str
    next_steps: list[str]


class LocalModelDownloadJobListResponse(BaseModel):
    jobs: list[LocalModelDownloadJobResponse]
    count: int
    running_count: int
    summary: str


def to_local_model_download_job_response(
    job: LocalModelDownloadJob,
) -> LocalModelDownloadJobResponse:
    return LocalModelDownloadJobResponse(
        id=job.id,
        command_id=job.command_id,
        workspace_id=job.workspace_id,
        provider=job.provider,
        model=job.model,
        display_name=job.display_name,
        status=job.status,
        progress_percent=job.progress_percent,
        progress_message=job.progress_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        command_proposal=to_command_proposal_response(job.command_proposal),
        stdout_preview=job.stdout_preview,
        stderr_preview=job.stderr_preview,
        exit_code=job.exit_code,
        cancel_requested_at=job.cancel_requested_at,
        cancellable=job.cancellable,
        cancellation_summary=job.cancellation_summary,
        safety_summary=job.safety_summary,
        next_steps=job.next_steps,
    )


def to_local_model_download_job_list_response(
    jobs: list[LocalModelDownloadJob],
) -> LocalModelDownloadJobListResponse:
    responses = [to_local_model_download_job_response(job) for job in jobs]
    running_count = len([job for job in jobs if job.status in {"queued", "running"}])
    return LocalModelDownloadJobListResponse(
        jobs=responses,
        count=len(responses),
        running_count=running_count,
        summary=(
            "No local model download jobs recorded yet."
            if not responses
            else f"{len(responses)} local model download job(s), {running_count} active."
        ),
    )
