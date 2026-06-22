"""Run a Project Watcher check.

Captures the current snapshot, rebuilds the project graph (the caller injects how
— typically rescan + build), diffs the new graph against the previous one and
persists a digest of what changed. Read-only with respect to the project: it only
reads files and writes to the local snapshot/digest store.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.core.domain.project_graph import ProjectSnapshotMeta
from app.core.domain.project_watch import build_watch_digest, diff_graphs
from app.core.ports.project_graph_repository import ProjectGraphRepositoryPort
from app.core.ports.project_watch_repository import ProjectWatchRepositoryPort


@dataclass(frozen=True)
class RunProjectWatchInput:
    workspace_id: str


class RunProjectWatchError(RuntimeError):
    pass


class RunProjectWatchUseCase:
    def __init__(
        self,
        project_graph_repository: ProjectGraphRepositoryPort,
        watch_repository: ProjectWatchRepositoryPort,
        build_graph: Callable[[str], ProjectSnapshotMeta],
    ) -> None:
        self.project_graph_repository = project_graph_repository
        self.watch_repository = watch_repository
        # build_graph rebuilds the graph for a workspace (e.g. rescan + build)
        # and returns the new snapshot meta. Injected so the use case stays
        # independent of scan/build wiring and is easy to test.
        self.build_graph = build_graph

    def execute(self, request: RunProjectWatchInput) -> dict:
        workspace_id = request.workspace_id
        previous_graph = self.project_graph_repository.get_latest_graph(workspace_id)
        previous_meta = self.project_graph_repository.get_latest_snapshot_meta(workspace_id)

        current_meta = self.build_graph(workspace_id)

        current_graph = self.project_graph_repository.get_latest_graph(workspace_id)
        if current_graph is None:
            raise RunProjectWatchError("The project graph could not be built")

        diff = diff_graphs(previous_graph, current_graph)
        digest = build_watch_digest(diff, previous_meta, current_meta)
        self.watch_repository.save_digest(workspace_id, digest)
        return digest
