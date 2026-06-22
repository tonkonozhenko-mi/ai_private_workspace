from typing import Protocol


class ProjectWatchRepositoryPort(Protocol):
    def save_digest(self, workspace_id: str, digest: dict) -> None:
        """Persist the latest watch digest for a workspace (replacing any prior)."""

    def get_latest_digest(self, workspace_id: str) -> dict | None:
        """Return the most recent watch digest, if any."""

    def clear(self, workspace_id: str) -> None:
        """Remove the stored watch digest for a workspace."""
