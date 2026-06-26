from typing import Protocol


class ProjectWatchRepositoryPort(Protocol):
    def save_digest(self, workspace_id: str, digest: dict) -> None:
        """Persist the latest watch digest for a workspace (replacing any prior)."""

    def get_latest_digest(self, workspace_id: str) -> dict | None:
        """Return the most recent watch digest, if any."""

    def clear(self, workspace_id: str) -> None:
        """Remove the stored watch digest *and* change history for a workspace."""

    # -- change history (append-only timeline of checks that found changes) ----

    def append_history(self, workspace_id: str, entry: dict) -> str:
        """Append a change-history entry; return its generated id."""

    def list_history(self, workspace_id: str, limit: int = 50) -> list[dict]:
        """Return change-history entries for a workspace, newest first."""

    def set_latest_history_summary(self, workspace_id: str, summary: str) -> None:
        """Attach an LLM ``llm_summary`` to the most recent history entry, if any."""

    # -- git-only history cursor (baseline HEAD for the cheap, git-only record) -

    def get_history_cursor(self, workspace_id: str) -> str | None:
        """The git HEAD recorded at the last git-only history record — the baseline
        for the next 'commits since' lookup. ``None`` if never recorded.

        This is deliberately separate from the watch digest's ``git_head`` so the
        cheap git-only journal and the full structural check don't fight over one
        slot."""

    def set_history_cursor(self, workspace_id: str, head: str | None) -> None:
        """Remember the git HEAD recorded for the change-history journal."""
