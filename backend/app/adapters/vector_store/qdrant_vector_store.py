from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.core.domain.indexing import ContextSearchResult, TextChunk


class QdrantVectorStore:
    def __init__(
        self,
        url: str,
        collection_name: str = "ai_workbench_chunks",
    ) -> None:
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name

    def upsert_chunks(
        self,
        workspace_id: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        if not embeddings[0]:
            raise ValueError("embedding vectors must not be empty")

        self._ensure_collection(vector_size=len(embeddings[0]))
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, chunk.id)),
                vector=embedding,
                payload={
                    "workspace_id": workspace_id,
                    "chunk_id": chunk.id,
                    "source_path": chunk.source_path,
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[ContextSearchResult]:
        if limit <= 0 or not query_embedding:
            return []
        if not self.client.collection_exists(self.collection_name):
            return []

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            query_filter=self._workspace_filter(workspace_id),
            limit=limit,
            with_payload=True,
        )

        return [
            ContextSearchResult(
                chunk_id=str(point.payload.get("chunk_id", "")),
                source_path=str(point.payload.get("source_path", "")),
                content=str(point.payload.get("content", "")),
                score=float(point.score),
                metadata={
                    str(key): str(value)
                    for key, value in dict(point.payload.get("metadata", {})).items()
                },
            )
            for point in response.points
            if point.payload is not None
        ]

    def clear_workspace(self, workspace_id: str) -> None:
        if not self.client.collection_exists(self.collection_name):
            return

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=self._workspace_filter(workspace_id),
            ),
            wait=True,
        )

    def _ensure_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.collection_name):
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    @staticmethod
    def _workspace_filter(workspace_id: str) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="workspace_id",
                    match=models.MatchValue(value=workspace_id),
                )
            ]
        )
