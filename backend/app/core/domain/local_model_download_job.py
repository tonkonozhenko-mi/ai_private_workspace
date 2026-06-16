from dataclasses import dataclass

from app.core.domain.command import CommandProposal


@dataclass(frozen=True)
class LocalModelDownloadJob:
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
    command_proposal: CommandProposal
    stdout_preview: str | None
    stderr_preview: str | None
    exit_code: int | None
    cancel_requested_at: str | None
    cancellable: bool
    cancellation_summary: str
    safety_summary: str
    next_steps: list[str]


def build_queued_model_download_job(
    *,
    job_id: str,
    command_id: str,
    workspace_id: str,
    provider: str,
    model: str,
    display_name: str,
    created_at: str,
    command_proposal: CommandProposal,
) -> LocalModelDownloadJob:
    return LocalModelDownloadJob(
        id=job_id,
        command_id=command_id,
        workspace_id=workspace_id,
        provider=provider,
        model=model,
        display_name=display_name,
        status="queued",
        progress_percent=0,
        progress_message="Download request recorded. Waiting for backend approval checks.",
        created_at=created_at,
        started_at=None,
        finished_at=None,
        command_proposal=command_proposal,
        stdout_preview=None,
        stderr_preview=None,
        exit_code=None,
        cancel_requested_at=None,
        cancellable=True,
        cancellation_summary=(
            "Queued downloads can be cancelled before the worker starts. Running Ollama pulls are not killed blindly; "
            "a cancel request is recorded and the worker finishes safely."
        ),
        safety_summary=(
            "The job is owned by the backend model download worker. The frontend only requests "
            "status and never executes shell commands."
        ),
        next_steps=[
            "Wait for the backend worker status.",
            "Re-check installed models after completion.",
        ],
    )
