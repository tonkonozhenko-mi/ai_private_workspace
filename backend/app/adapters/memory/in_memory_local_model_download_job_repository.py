from app.core.domain.local_model_download_job import LocalModelDownloadJob


class InMemoryLocalModelDownloadJobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, LocalModelDownloadJob] = {}

    def create(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> LocalModelDownloadJob | None:
        return self._jobs.get(job_id)

    def update(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        self._jobs[job.id] = job
        return job
