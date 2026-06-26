"""In-memory index manifest (tests / memory mode)."""

from app.core.ports.index_manifest_repository import ManifestEntry


class InMemoryIndexManifestRepository:
    def __init__(self) -> None:
        self._entries: dict[str, dict[str, ManifestEntry]] = {}

    def get(self, workspace_id: str) -> dict[str, ManifestEntry]:
        return {path: dict(entry) for path, entry in self._entries.get(workspace_id, {}).items()}

    def replace_all(self, workspace_id: str, entries: dict[str, ManifestEntry]) -> None:
        self._entries[workspace_id] = {path: dict(entry) for path, entry in entries.items()}

    def upsert(self, workspace_id: str, source_path: str, content_hash: str, chunks: int) -> None:
        self._entries.setdefault(workspace_id, {})[source_path] = {
            "hash": content_hash,
            "chunks": chunks,
        }

    def delete(self, workspace_id: str, source_paths: list[str]) -> None:
        bucket = self._entries.get(workspace_id)
        if not bucket:
            return
        for path in source_paths:
            bucket.pop(path, None)

    def clear(self, workspace_id: str) -> None:
        self._entries.pop(workspace_id, None)
