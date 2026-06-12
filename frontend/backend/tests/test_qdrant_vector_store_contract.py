import os
from uuid import uuid4

import pytest

from app.adapters.vector_store.in_memory_vector_store import InMemoryVectorStore
from app.adapters.vector_store.qdrant_collection_naming import (
    build_qdrant_collection_name,
)
from app.api.dependencies import build_vector_store
from app.config.settings import get_settings
from app.core.domain.indexing import TextChunk


RUN_QDRANT_TESTS = os.getenv("RUN_QDRANT_TESTS", "").lower() == "true"


def test_build_vector_store_uses_memory_by_default(monkeypatch) -> None:
    monkeypatch.delenv("VECTOR_STORE", raising=False)
    get_settings.cache_clear()

    vector_store = build_vector_store()

    assert isinstance(vector_store, InMemoryVectorStore)
    get_settings.cache_clear()


@pytest.mark.skipif(
    not RUN_QDRANT_TESTS,
    reason="Set RUN_QDRANT_TESTS=true to run Qdrant contract tests.",
)
def test_qdrant_vector_store_contract() -> None:
    from qdrant_client import QdrantClient

    from app.adapters.vector_store.qdrant_vector_store import QdrantVectorStore

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection_name = f"ai_workbench_test_{uuid4().hex}"
    client = QdrantClient(url=qdrant_url)
    vector_store = QdrantVectorStore(
        url=qdrant_url,
        collection_name=collection_name,
    )
    fake_collection_name = build_qdrant_collection_name(
        base_collection_name=collection_name,
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=3,
    )
    ollama_collection_name = build_qdrant_collection_name(
        base_collection_name=collection_name,
        embedding_provider="ollama",
        embedding_model="nomic-embed-text",
        embedding_dimension=4,
    )

    workspace_a_chunk = _chunk(
        chunk_id="workspace-a:README.md:0",
        workspace_id="workspace-a",
        source_path="README.md",
        content="Terraform infrastructure documentation.",
    )
    workspace_b_chunk = _chunk(
        chunk_id="workspace-b:README.md:0",
        workspace_id="workspace-b",
        source_path="README.md",
        content="Other workspace content.",
    )

    try:
        vector_store.upsert_chunks(
            workspace_id="workspace-a",
            chunks=[workspace_a_chunk],
            embeddings=[[1.0, 0.0, 0.0]],
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_dimension=3,
        )
        vector_store.upsert_chunks(
            workspace_id="workspace-b",
            chunks=[workspace_b_chunk],
            embeddings=[[1.0, 0.0, 0.0]],
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_dimension=3,
        )

        workspace_a_results = vector_store.search(
            workspace_id="workspace-a",
            query_embedding=[1.0, 0.0, 0.0],
            limit=5,
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_dimension=3,
        )

        assert [result.chunk_id for result in workspace_a_results] == [
            workspace_a_chunk.id
        ]
        assert workspace_a_results[0].source_path == "README.md"
        assert workspace_a_results[0].metadata == {"detected_type": "markdown"}

        vector_store.clear_workspace(
            "workspace-a",
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_dimension=3,
        )

        assert (
            vector_store.search(
                workspace_id="workspace-a",
                query_embedding=[1.0, 0.0, 0.0],
                limit=5,
                embedding_provider="fake",
                embedding_model="fake-embedding",
                embedding_dimension=3,
            )
            == []
        )
        assert vector_store.search(
            workspace_id="workspace-b",
            query_embedding=[1.0, 0.0, 0.0],
            limit=5,
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_dimension=3,
        )

        vector_store.upsert_chunks(
            workspace_id="workspace-a",
            chunks=[workspace_a_chunk],
            embeddings=[[1.0, 0.0, 0.0, 0.0]],
            embedding_provider="ollama",
            embedding_model="nomic-embed-text",
            embedding_dimension=4,
        )

        assert client.collection_exists(fake_collection_name)
        assert client.collection_exists(ollama_collection_name)
    finally:
        for test_collection_name in [fake_collection_name, ollama_collection_name]:
            if client.collection_exists(test_collection_name):
                client.delete_collection(test_collection_name)


def _chunk(
    chunk_id: str,
    workspace_id: str,
    source_path: str,
    content: str,
) -> TextChunk:
    return TextChunk(
        id=chunk_id,
        workspace_id=workspace_id,
        source_path=source_path,
        chunk_index=0,
        content=content,
        token_estimate=max(1, len(content) // 4),
        metadata={"detected_type": "markdown"},
    )
