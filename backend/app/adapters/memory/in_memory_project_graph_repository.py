"""In-memory Project Intelligence graph store (tests / memory mode)."""

import uuid
from datetime import datetime, timezone

from app.core.domain.project_graph import ProjectGraph, ProjectSnapshotMeta


class InMemoryProjectGraphRepository:
    def __init__(self) -> None:
        self._latest: dict[str, tuple[ProjectGraph, ProjectSnapshotMeta]] = {}

    def save_graph(
        self, graph: ProjectGraph, scan_signature: str | None = None
    ) -> ProjectSnapshotMeta:
        meta = ProjectSnapshotMeta(
            id=str(uuid.uuid4()),
            workspace_id=graph.workspace_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            entity_count=len(graph.entities),
            relation_count=len(graph.relations),
            finding_count=len(graph.findings),
            analyzers_run=list(graph.analyzers_run),
            analyzers_skipped=list(graph.analyzers_skipped),
            scan_signature=scan_signature,
        )
        self._latest[graph.workspace_id] = (graph, meta)
        return meta

    def get_latest_graph(self, workspace_id: str) -> ProjectGraph | None:
        entry = self._latest.get(workspace_id)
        return entry[0] if entry else None

    def get_latest_snapshot_meta(self, workspace_id: str) -> ProjectSnapshotMeta | None:
        entry = self._latest.get(workspace_id)
        return entry[1] if entry else None

    def clear(self, workspace_id: str) -> None:
        self._latest.pop(workspace_id, None)
