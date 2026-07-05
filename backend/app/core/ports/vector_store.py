from typing import Protocol

from app.core.domain.indexing import ContextSearchResult, SourceChunk, TextChunk


class VectorStoreCorruptError(Exception):
    """The vector index file is damaged and can't be read.

    Adapters raise this (instead of leaking a backend-specific error like
    ``sqlite3.DatabaseError``) when the underlying store reports corruption, so
    callers can respond with a clear "rebuild the index" message rather than a
    raw 500. The only cure is to re-index the workspace.
    """


class VectorStorePort(Protocol):
    def upsert_chunks(
        self,
        workspace_id: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        """Store embedded text chunks for a workspace."""

    def search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        limit: int,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
        query_text: str | None = None,
    ) -> list[ContextSearchResult]:
        """Return the most relevant chunks for a workspace.

        ``query_text`` is the original question; stores that support hybrid
        (keyword + vector) search use it for the keyword side. Vector-only stores
        ignore it.
        """

    def clear_workspace(
        self,
        workspace_id: str,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        """Remove all stored chunks for a workspace."""

    def delete_chunks_by_source_path(self, workspace_id: str, source_paths: list[str]) -> None:
        """Remove all chunks whose source file is in ``source_paths``.

        Used by incremental re-indexing to drop the old chunks of changed or
        removed files before re-embedding only what changed. A no-op for paths
        with no stored chunks."""

    def get_source_chunks(self, workspace_id: str, source_path: str) -> list[SourceChunk]:
        """Return all chunks of one file, ordered by chunk_index.

        Powers parent-document (small-to-big) retrieval: a retrieved chunk is
        expanded with its neighbours in the same file so the model sees enough
        surrounding context. Returns an empty list when the file has no chunks."""


VectorStore = VectorStorePort
