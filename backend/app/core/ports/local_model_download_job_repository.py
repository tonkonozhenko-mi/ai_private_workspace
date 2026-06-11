from typing import Protocol

from app.core.domain.local_model_download_job import LocalModelDownloadJob


class LocalModelDownloadJobRepositoryPort(Protocol):
    def create(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        """Persist a local model download job."""

    def get(self, job_id: str) -> LocalModelDownloadJob | None:
        """Return a job by id, if it exists."""

    def update(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        """Persist an updated job."""
