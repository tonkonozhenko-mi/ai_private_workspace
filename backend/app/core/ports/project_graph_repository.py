from typing import Protocol

from app.core.domain.project_graph import ProjectGraph, ProjectSnapshotMeta


class ProjectGraphRepositoryPort(Protocol):
    def save_graph(
        self, graph: ProjectGraph, scan_signature: str | None = None
    ) -> ProjectSnapshotMeta:
        """Persist a project graph as the latest snapshot for its workspace."""

    def get_latest_graph(self, workspace_id: str) -> ProjectGraph | None:
        """Return the most recent persisted project graph, if any."""

    def get_latest_snapshot_meta(self, workspace_id: str) -> ProjectSnapshotMeta | None:
        """Return metadata for the most recent snapshot, if any."""

    def clear(self, workspace_id: str) -> None:
        """Remove all persisted project graphs for a workspace."""
