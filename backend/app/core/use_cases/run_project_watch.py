"""Run a Project Watcher check.

Captures the current snapshot, rebuilds the project graph (the caller injects how
— typically rescan + build), diffs the new graph against the previous one and
persists a digest of what changed. Read-only with respect to the project: it only
reads files and writes to the local snapshot/digest store.
"""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass

from app.core.domain.project_graph import ProjectSnapshotMeta
from app.core.domain.project_watch import (
    build_watch_digest,
    build_watch_history_entry,
    diff_graphs,
)
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
        git_brief_provider: "Callable[[str, str | None], object] | None" = None,
    ) -> None:
        self.project_graph_repository = project_graph_repository
        self.watch_repository = watch_repository
        # build_graph rebuilds the graph for a workspace (e.g. rescan + build)
        # and returns the new snapshot meta. Injected so the use case stays
        # independent of scan/build wiring and is easy to test.
        self.build_graph = build_graph
        # git_brief_provider(workspace_id, since_commit) -> GitChangeBrief. Injected
        # so the use case stays free of git/filesystem wiring. Optional: without it
        # the digest is graph-only (back-compatible).
        self.git_brief_provider = git_brief_provider

    def ensure_baseline(self, workspace_id: str) -> dict | None:
        """Record where the project stood, the first time we ever see it.

        "What changed since you were here" needs a *here* — and until now the only way
        to get one was to press Refresh, which re-scans the whole project. So the first
        session recorded nothing, and the second session could only offer to start
        counting from then. The baseline costs nothing: the graph has already been
        built, so this reads it, notes the current commit, and saves that as the mark
        to measure from. Nothing is re-scanned and nothing is rebuilt.

        Returns None when there is nothing to baseline (no graph yet) or when a digest
        already exists — a baseline may never overwrite a real history.
        """
        if self.watch_repository.get_latest_digest(workspace_id) is not None:
            return None
        graph = self.project_graph_repository.get_latest_graph(workspace_id)
        meta = self.project_graph_repository.get_latest_snapshot_meta(workspace_id)
        if graph is None or meta is None:
            return None

        git_brief = None
        if self.git_brief_provider is not None:
            try:
                git_brief = self.git_brief_provider(workspace_id, None)
            except Exception:  # noqa: BLE001 - git is best-effort; never fail this
                git_brief = None

        digest = build_watch_digest(
            diff_graphs(None, graph), None, meta, git_brief=git_brief
        )
        self.watch_repository.save_digest(workspace_id, digest)
        return digest

    def execute(self, request: RunProjectWatchInput) -> dict:
        workspace_id = request.workspace_id
        previous_graph = self.project_graph_repository.get_latest_graph(workspace_id)
        previous_meta = self.project_graph_repository.get_latest_snapshot_meta(workspace_id)
        # The HEAD commit recorded at the last check is the baseline for "what
        # changed in git since then".
        previous_digest = self.watch_repository.get_latest_digest(workspace_id)
        since_commit = (
            previous_digest.get("git_head") if isinstance(previous_digest, dict) else None
        )

        current_meta = self.build_graph(workspace_id)

        current_graph = self.project_graph_repository.get_latest_graph(workspace_id)
        if current_graph is None:
            raise RunProjectWatchError("The project graph could not be built")

        git_brief = None
        if self.git_brief_provider is not None:
            try:
                git_brief = self.git_brief_provider(workspace_id, since_commit)
            except Exception:  # noqa: BLE001 - git is best-effort; never fail a check
                git_brief = None

        diff = diff_graphs(previous_graph, current_graph)
        digest = build_watch_digest(diff, previous_meta, current_meta, git_brief=git_brief)
        self.watch_repository.save_digest(workspace_id, digest)

        # Log a timeline entry whenever something actually changed, so the
        # history tab keeps a durable record instead of the digest vanishing on
        # the next check. Best-effort: a logging failure must not fail the check.
        entry = build_watch_history_entry(digest)
        if entry is not None and hasattr(self.watch_repository, "append_history"):
            with contextlib.suppress(Exception):  # history is best-effort
                self.watch_repository.append_history(workspace_id, entry)
        return digest
