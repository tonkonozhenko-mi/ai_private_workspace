from math import sqrt

from app.core.domain.indexing import ContextSearchResult, TextChunk

StoredChunk = tuple[TextChunk, list[float]]


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: dict[str, list[StoredChunk]] = {}

    def upsert_chunks(
        self,
        workspace_id: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        new_chunk_ids = {chunk.id for chunk in chunks}
        existing_chunks = [
            stored_chunk
            for stored_chunk in self._chunks.get(workspace_id, [])
            if stored_chunk[0].id not in new_chunk_ids
        ]
        self._chunks[workspace_id] = [
            *existing_chunks,
            *zip(chunks, embeddings),
        ]

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
        # query_text is accepted for interface parity; this store is vector-only.
        if limit <= 0:
            return []

        scored_chunks = [
            (
                self._cosine_similarity(query_embedding, embedding),
                chunk,
            )
            for chunk, embedding in self._chunks.get(workspace_id, [])
        ]
        scored_chunks.sort(key=lambda item: item[0], reverse=True)

        return [
            ContextSearchResult(
                chunk_id=chunk.id,
                source_path=chunk.source_path,
                content=chunk.content,
                score=score,
                metadata=chunk.metadata,
            )
            for score, chunk in scored_chunks[:limit]
        ]

    def clear_workspace(
        self,
        workspace_id: str,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        self._chunks.pop(workspace_id, None)

    @staticmethod
    def _cosine_similarity(first: list[float], second: list[float]) -> float:
        if not first or not second:
            return 0.0

        dimensions = min(len(first), len(second))
        dot_product = sum(first[index] * second[index] for index in range(dimensions))
        first_norm = sqrt(sum(value * value for value in first))
        second_norm = sqrt(sum(value * value for value in second))

        if first_norm == 0.0 or second_norm == 0.0:
            return 0.0
        return dot_product / (first_norm * second_norm)
