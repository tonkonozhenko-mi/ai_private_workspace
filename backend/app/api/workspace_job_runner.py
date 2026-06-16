from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}
logger = logging.getLogger("uvicorn.error.ai_private_workspace.workspace_jobs")


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class WorkspaceJob:
    job_id: str
    workspace_id: str
    job_type: str
    title: str
    status: str = "queued"
    message: str | None = None
    result_summary: dict[str, str] = field(default_factory=dict)
    request_summary: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    cancellation_requested: bool = False
    progress_current: int | None = None
    progress_total: int | None = None
    progress_percent: float | None = None
    current_step: str | None = None
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None


class WorkspaceJobNotFoundError(KeyError):
    pass


class WorkspaceJobCancelledError(RuntimeError):
    pass


class WorkspaceJobControl:
    def __init__(self, runner: WorkspaceJobRunner, job_id: str) -> None:
        self._runner = runner
        self._job_id = job_id

    def is_cancellation_requested(self) -> bool:
        return self._runner.is_cancellation_requested(self._job_id)

    def checkpoint(self, message: str | None = None) -> None:
        if message is not None:
            self.update_progress(message=message)
        if self.is_cancellation_requested():
            raise WorkspaceJobCancelledError("Workspace job cancelled")

    def update_progress(
        self,
        *,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
        current_step: str | None = None,
    ) -> None:
        self._runner.update_progress(
            self._job_id,
            current=current,
            total=total,
            message=message,
            current_step=current_step,
        )


class WorkspaceJobRunner:
    def __init__(self, max_workers: int = 2) -> None:
        self._jobs: dict[str, WorkspaceJob] = {}
        self._lock = Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def start_job(
        self,
        *,
        workspace_id: str,
        job_type: str,
        title: str,
        message: str,
        operation: Callable[[WorkspaceJobControl], dict[str, str]],
        request_summary: dict[str, str] | None = None,
    ) -> WorkspaceJob:
        job = WorkspaceJob(
            job_id=str(uuid4()),
            workspace_id=workspace_id,
            job_type=job_type,
            title=title,
            message=message,
            request_summary=request_summary or {},
        )
        with self._lock:
            self._jobs[job.job_id] = job

        logger.info(
            "workspace job queued workspace_id=%s job_id=%s job_type=%s",
            workspace_id,
            job.job_id,
            job_type,
        )
        self._executor.submit(self._run_job, job.job_id, operation)
        return self.get_job(job.job_id)

    def list_workspace_jobs(self, workspace_id: str) -> list[WorkspaceJob]:
        with self._lock:
            jobs = [job for job in self._jobs.values() if job.workspace_id == workspace_id]
        return sorted(jobs, key=lambda item: item.created_at, reverse=True)

    def get_job(self, job_id: str) -> WorkspaceJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise WorkspaceJobNotFoundError(job_id)
            return WorkspaceJob(**job.__dict__)

    def cancel_job(self, job_id: str) -> WorkspaceJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise WorkspaceJobNotFoundError(job_id)
            if job.status == "queued":
                job.status = "cancelled"
                job.cancellation_requested = True
                job.message = "Cancelled before the operation started."
                job.completed_at = _now()
                job.duration_ms = _duration_ms(job.started_at or job.created_at, job.completed_at)
            elif job.status == "running":
                job.cancellation_requested = True
                job.message = (
                    "Cancellation requested. The backend will stop when the current "
                    "safe operation checkpoint allows it."
                )
        return self.get_job(job_id)

    def is_cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.cancellation_requested)

    def update_progress(
        self,
        job_id: str,
        *,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
        current_step: str | None = None,
    ) -> WorkspaceJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise WorkspaceJobNotFoundError(job_id)
            if current is not None:
                job.progress_current = current
            if total is not None:
                job.progress_total = total
            if message is not None:
                job.message = message
            if current_step is not None:
                job.current_step = current_step
            if job.progress_current is not None and job.progress_total:
                job.progress_percent = min(
                    100.0, round((job.progress_current / job.progress_total) * 100, 1)
                )
        return self.get_job(job_id)

    def _run_job(
        self, job_id: str, operation: Callable[[WorkspaceJobControl], dict[str, str]]
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if job.status == "cancelled":
                return
            job.status = "running"
            job.started_at = _now()
            job.message = "Running..."
            workspace_id = job.workspace_id
            job_type = job.job_type

        logger.info(
            "workspace job started workspace_id=%s job_id=%s job_type=%s",
            workspace_id,
            job_id,
            job_type,
        )

        try:
            with self._lock:
                current = self._jobs[job_id]
                if current.cancellation_requested:
                    current.status = "cancelled"
                    current.message = "Cancelled before the operation started."
                    current.completed_at = _now()
                    current.duration_ms = _duration_ms(
                        current.started_at or current.created_at, current.completed_at
                    )
                    return
            result_summary = operation(WorkspaceJobControl(self, job_id))
        except WorkspaceJobCancelledError:
            with self._lock:
                cancelled_job = self._jobs[job_id]
                cancelled_job.status = "cancelled"
                cancelled_job.cancellation_requested = True
                cancelled_job.message = "Cancelled at a safe operation checkpoint."
                cancelled_job.completed_at = _now()
                cancelled_job.duration_ms = _duration_ms(
                    cancelled_job.started_at or cancelled_job.created_at, cancelled_job.completed_at
                )
            return
        except Exception as exc:  # noqa: BLE001 - error is surfaced to API as job status
            with self._lock:
                failed = self._jobs[job_id]
                failed.status = "failed"
                failed.error = str(exc)
                failed.message = "The operation failed."
                failed.completed_at = _now()
                failed.duration_ms = _duration_ms(
                    failed.started_at or failed.created_at, failed.completed_at
                )
                workspace_id = failed.workspace_id
                job_type = failed.job_type
                duration_ms = failed.duration_ms
            logger.exception(
                "workspace job failed workspace_id=%s job_id=%s job_type=%s duration_ms=%s",
                workspace_id,
                job_id,
                job_type,
                duration_ms,
            )
            return

        with self._lock:
            completed = self._jobs[job_id]
            if completed.cancellation_requested:
                completed.message = (
                    "Cancellation was requested, but the operation finished before "
                    "it could be stopped."
                )
            else:
                completed.message = "Completed."
            completed.status = "completed"
            completed.result_summary = result_summary
            completed.progress_percent = 100.0
            completed.completed_at = _now()
            completed.duration_ms = _duration_ms(
                completed.started_at or completed.created_at, completed.completed_at
            )
            workspace_id = completed.workspace_id
            job_type = completed.job_type
            duration_ms = completed.duration_ms

        logger.info(
            "workspace job completed workspace_id=%s job_id=%s job_type=%s duration_ms=%s result=%s",
            workspace_id,
            job_id,
            job_type,
            duration_ms,
            result_summary,
        )


def _duration_ms(started_at: str | None, completed_at: str | None) -> int | None:
    if not started_at or not completed_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at)
    except ValueError:
        return None
    return max(0, int((completed - start).total_seconds() * 1000))
