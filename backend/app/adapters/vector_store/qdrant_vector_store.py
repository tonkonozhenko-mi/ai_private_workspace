from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.adapters.vector_store.qdrant_collection_naming import (
    build_qdrant_collection_name,
)
from app.core.domain.indexing import ContextSearchResult, TextChunk


class QdrantVectorStoreError(RuntimeError):
    pass


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
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return
        if not embeddings[0]:
            raise ValueError("embedding vectors must not be empty")

        actual_dimension = len(embeddings[0])
        if any(len(embedding) != actual_dimension for embedding in embeddings):
            raise QdrantVectorStoreError(
                "Cannot index embeddings with inconsistent vector dimensions"
            )
        self._validate_requested_dimension(embedding_dimension, actual_dimension)
        collection_name = self._collection_name(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimension=actual_dimension,
        )
        self._ensure_collection(
            collection_name=collection_name,
            vector_size=actual_dimension,
        )
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
            collection_name=collection_name,
            points=points,
            wait=True,
        )

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
        if limit <= 0 or not query_embedding:
            return []

        actual_dimension = len(query_embedding)
        self._validate_requested_dimension(embedding_dimension, actual_dimension)
        collection_name = self._collection_name(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimension=actual_dimension,
        )
        if not self.client.collection_exists(collection_name):
            return []
        self._validate_collection_dimension(collection_name, actual_dimension)

        response = self.client.query_points(
            collection_name=collection_name,
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

    def clear_workspace(
        self,
        workspace_id: str,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        collection_name = self._collection_name(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
        )
        if not self.client.collection_exists(collection_name):
            return
        if embedding_dimension is not None:
            self._validate_collection_dimension(collection_name, embedding_dimension)

        self.client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=self._workspace_filter(workspace_id),
            ),
            wait=True,
        )

    def delete_chunks_by_source_path(self, workspace_id: str, source_paths: list[str]) -> None:
        paths = [p for p in dict.fromkeys(source_paths) if p]
        if not paths:
            return
        # The collection is per embedding (provider/model/dim); without those we
        # can't name it precisely, so clear matching points across any collections
        # that exist for this client. In practice one collection is active.
        for collection_name in self._existing_collection_names():
            self.client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="workspace_id",
                                match=models.MatchValue(value=workspace_id),
                            ),
                            models.FieldCondition(
                                key="source_path",
                                match=models.MatchAny(any=paths),
                            ),
                        ]
                    ),
                ),
                wait=True,
            )

    def _existing_collection_names(self) -> list[str]:
        try:
            return [c.name for c in self.client.get_collections().collections]
        except Exception:  # noqa: BLE001 - best-effort listing
            return []

    def _ensure_collection(self, collection_name: str, vector_size: int) -> None:
        if self.client.collection_exists(collection_name):
            self._validate_collection_dimension(collection_name, vector_size)
            return

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def _validate_collection_dimension(
        self,
        collection_name: str,
        expected_dimension: int,
    ) -> None:
        collection_info = self.client.get_collection(collection_name)
        vectors_config = collection_info.config.params.vectors
        actual_dimension = self._vector_size(vectors_config)

        if actual_dimension != expected_dimension:
            raise QdrantVectorStoreError(
                f"Qdrant collection '{collection_name}' has vector dimension "
                f"{actual_dimension}, expected {expected_dimension}. "
                "Use embedding-aware collection metadata or a different collection name."
            )

    @staticmethod
    def _vector_size(vectors_config) -> int | None:
        vector_size = getattr(vectors_config, "size", None)
        if vector_size is not None:
            return int(vector_size)
        if isinstance(vectors_config, dict) and len(vectors_config) == 1:
            named_vector = next(iter(vectors_config.values()))
            named_vector_size = getattr(named_vector, "size", None)
            if named_vector_size is None and isinstance(named_vector, dict):
                named_vector_size = named_vector.get("size")
            if named_vector_size is not None:
                return int(named_vector_size)
        return None

    @staticmethod
    def _validate_requested_dimension(
        requested_dimension: int | None,
        actual_dimension: int,
    ) -> None:
        if requested_dimension is not None and requested_dimension != actual_dimension:
            raise QdrantVectorStoreError(
                f"Embedding dimension metadata is {requested_dimension}, "
                f"but the actual vector dimension is {actual_dimension}"
            )

    def _collection_name(
        self,
        embedding_provider: str | None,
        embedding_model: str | None,
        embedding_dimension: int | None,
    ) -> str:
        return build_qdrant_collection_name(
            base_collection_name=self.collection_name,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            embedding_dimension=embedding_dimension,
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
