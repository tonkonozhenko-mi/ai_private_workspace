"""Record a change-history entry from git alone - the cheap path.

Unlike the full Project Watch check (which rescans the files and rebuilds the
project graph), this only reads git: "which commits landed since we last
recorded?". No file rescan, no graph rebuild, no RAG re-indexing. It is meant to
run often (e.g. when the app opens) so the dated history journal fills itself
without expensive work. The full check stays the way to refresh the project
graph and structural findings for the other features.
"""

import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.domain.project_memory import memories_referencing_paths
from app.core.domain.project_watch import build_git_only_digest, build_watch_history_entry
from app.core.ports.project_watch_repository import ProjectWatchRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class RecordGitHistoryInput:
    workspace_id: str


class RecordGitHistoryWorkspaceNotFoundError(ValueError):
    pass


class RecordGitHistoryUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        watch_repository: ProjectWatchRepositoryPort,
        git_brief_provider,
        project_memory_repository=None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.watch_repository = watch_repository
        # git_brief_provider(workspace_id, since_commit) -> GitChangeBrief (pure git).
        self.git_brief_provider = git_brief_provider
        # Optional: when present, memories that reference a changed file are flagged
        # 'stale' so the user can confirm they're still true. Best-effort.
        self.project_memory_repository = project_memory_repository

    def execute(self, request: RecordGitHistoryInput) -> dict:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise RecordGitHistoryWorkspaceNotFoundError("Workspace not found")

        wid = request.workspace_id
        since = self.watch_repository.get_history_cursor(wid)
        git_brief = self.git_brief_provider(wid, since)

        now = datetime.now(timezone.utc).isoformat()
        previous = self.watch_repository.get_latest_digest(wid)
        previous_checked = previous.get("checked_at") if isinstance(previous, dict) else None
        digest = build_git_only_digest(git_brief, now, previous_checked)

        # Advance the journal cursor even on a baseline / no-change read, so the
        # next lookup starts from the current HEAD instead of re-listing commits.
        head = git_brief.head if git_brief is not None else None
        if head:
            self.watch_repository.set_history_cursor(wid, head)

        entry = build_watch_history_entry(digest)
        if entry is not None:
            with contextlib.suppress(Exception):  # history is best-effort
                self.watch_repository.append_history(wid, entry)

        # Auto-stale: flag memories that reference a file that just changed, so the
        # user is prompted to confirm they're still true. Best-effort; never fails
        # the history record.
        changed_paths = getattr(git_brief, "changed_paths", None) if git_brief else None
        if self.project_memory_repository is not None and changed_paths:
            with contextlib.suppress(Exception):
                items = self.project_memory_repository.list(wid)
                for item_id in memories_referencing_paths(items, changed_paths):
                    self.project_memory_repository.set_stale(wid, item_id, True)
        return digest
