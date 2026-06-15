from typing import Protocol

from app.core.domain.workspace_storage import WorkspaceStorageBreakdown


class WorkspaceStorageGatewayPort(Protocol):
    def get_or_compute(self, workspace_id: str) -> WorkspaceStorageBreakdown:
        """Return a cached breakdown, computing and caching it if missing."""

    def get_cached(self, workspace_id: str) -> WorkspaceStorageBreakdown | None:
        """Return the cached breakdown for a workspace, if one exists."""

    def recompute(self, workspace_id: str) -> WorkspaceStorageBreakdown:
        """Recompute the breakdown from current data and refresh the cache."""

    def delete_workspace_data(self, workspace_id: str) -> None:
        """Delete all per-workspace rows owned by this gateway (including cache)."""

    def invalidate(self, workspace_id: str) -> None:
        """Drop the cached breakdown so the next read recomputes it."""
