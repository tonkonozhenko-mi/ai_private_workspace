from threading import RLock

from app.core.domain.local_model_download_job import LocalModelDownloadJob


class InMemoryLocalModelDownloadJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, LocalModelDownloadJob] = {}
        self._lock = RLock()

    def create(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        with self._lock:
            self._jobs[job.id] = job
            return job

    def get(self, job_id: str) -> LocalModelDownloadJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        with self._lock:
            self._jobs[job.id] = job
            return job

    def list(self, workspace_id: str | None = None) -> list[LocalModelDownloadJob]:
        with self._lock:
            jobs = list(self._jobs.values())
        if workspace_id is not None:
            jobs = [job for job in jobs if job.workspace_id == workspace_id]
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)
