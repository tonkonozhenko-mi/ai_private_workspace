from typing import Protocol

from app.core.domain.index_status import WorkspaceIndexStatus


class IndexStatusRepositoryPort(Protocol):
    def save(self, status: WorkspaceIndexStatus) -> WorkspaceIndexStatus:
        """Persist workspace index status metadata."""

    def get(self, workspace_id: str) -> WorkspaceIndexStatus | None:
        """Return workspace index status metadata, if it exists."""
