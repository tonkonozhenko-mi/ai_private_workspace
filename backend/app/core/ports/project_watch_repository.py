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
