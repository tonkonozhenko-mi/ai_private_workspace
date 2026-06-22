"""In-memory Project Watcher digest store (tests / memory mode)."""


class InMemoryProjectWatchRepository:
    def __init__(self) -> None:
        self._digests: dict[str, dict] = {}

    def save_digest(self, workspace_id: str, digest: dict) -> None:
        self._digests[workspace_id] = dict(digest)

    def get_latest_digest(self, workspace_id: str) -> dict | None:
        return self._digests.get(workspace_id)

    def clear(self, workspace_id: str) -> None:
        self._digests.pop(workspace_id, None)
