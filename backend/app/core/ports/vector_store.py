from typing import Protocol

from app.core.domain.indexing import ContextSearchResult, TextChunk


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


VectorStore = VectorStorePort
