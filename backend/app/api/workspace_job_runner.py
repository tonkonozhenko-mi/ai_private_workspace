from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from uuid import uuid4


TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}


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
    error: str | None = None
    cancellation_requested: bool = False
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    completed_at: str | None = None


class WorkspaceJobNotFoundError(KeyError):
    pass


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
        operation: Callable[[], dict[str, str]],
    ) -> WorkspaceJob:
        job = WorkspaceJob(
            job_id=str(uuid4()),
            workspace_id=workspace_id,
            job_type=job_type,
            title=title,
            message=message,
        )
        with self._lock:
            self._jobs[job.job_id] = job

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
            elif job.status == "running":
                job.cancellation_requested = True
                job.message = (
                    "Cancellation requested. The backend will stop when the current "
                    "safe operation checkpoint allows it."
                )
        return self.get_job(job_id)

    def _run_job(self, job_id: str, operation: Callable[[], dict[str, str]]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if job.status == "cancelled":
                return
            job.status = "running"
            job.started_at = _now()
            job.message = "Running..."

        try:
            with self._lock:
                current = self._jobs[job_id]
                if current.cancellation_requested:
                    current.status = "cancelled"
                    current.message = "Cancelled before the operation started."
                    current.completed_at = _now()
                    return
            result_summary = operation()
        except Exception as exc:  # noqa: BLE001 - error is surfaced to API as job status
            with self._lock:
                failed = self._jobs[job_id]
                failed.status = "failed"
                failed.error = str(exc)
                failed.message = "The operation failed."
                failed.completed_at = _now()
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
            completed.completed_at = _now()
