"""Tracks what is currently indexed per workspace, so re-indexing can be
incremental: re-embed only files whose content hash changed, drop chunks for
files that were removed, and leave the rest untouched.

Each entry maps a ``source_path`` to ``{"hash": <content sha256>, "chunks": N}``.
``chunks`` lets us keep the index status totals accurate without re-counting the
vector store.
"""

from typing import Protocol

ManifestEntry = dict[str, object]  # {"hash": str, "chunks": int}


class IndexManifestRepositoryPort(Protocol):
    def get(self, workspace_id: str) -> dict[str, ManifestEntry]:
        """Return ``{source_path: {"hash", "chunks"}}`` for the workspace."""

    def replace_all(self, workspace_id: str, entries: dict[str, ManifestEntry]) -> None:
        """Replace the whole manifest for a workspace (used after a full index)."""

    def upsert(self, workspace_id: str, source_path: str, content_hash: str, chunks: int) -> None:
        """Record/refresh one file's indexed hash and chunk count."""

    def delete(self, workspace_id: str, source_paths: list[str]) -> None:
        """Forget the given files (they were removed from the project)."""

    def clear(self, workspace_id: str) -> None:
        """Drop the whole manifest for a workspace."""
