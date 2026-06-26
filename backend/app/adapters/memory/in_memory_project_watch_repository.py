"""In-memory Project Watcher digest + history store (tests / memory mode)."""

import uuid
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemoryProjectWatchRepository:
    def __init__(self) -> None:
        self._digests: dict[str, dict] = {}
        # Newest entries first, per workspace.
        self._history: dict[str, list[dict]] = {}

    def save_digest(self, workspace_id: str, digest: dict) -> None:
        self._digests[workspace_id] = dict(digest)

    def get_latest_digest(self, workspace_id: str) -> dict | None:
        return self._digests.get(workspace_id)

    def clear(self, workspace_id: str) -> None:
        self._digests.pop(workspace_id, None)
        self._history.pop(workspace_id, None)

    def append_history(self, workspace_id: str, entry: dict) -> str:
        entry_id = str(uuid.uuid4())
        record = {**dict(entry), "id": entry_id, "created_at": _utc_now_iso()}
        self._history.setdefault(workspace_id, []).insert(0, record)
        return entry_id

    def list_history(self, workspace_id: str, limit: int = 50) -> list[dict]:
        return [dict(e) for e in self._history.get(workspace_id, [])[: max(0, limit)]]

    def set_latest_history_summary(self, workspace_id: str, summary: str) -> None:
        entries = self._history.get(workspace_id)
        if entries:
            entries[0]["llm_summary"] = summary
