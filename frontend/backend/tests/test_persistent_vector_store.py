from app.adapters.vector_store.in_memory_vector_store import InMemoryVectorStore
from app.adapters.vector_store.sqlite_vector_store import SQLiteVectorStore
from app.core.domain.indexing import TextChunk


def _chunk(workspace_id: str, chunk_id: str, content: str, source_path: str = "README.md") -> TextChunk:
    return TextChunk(
        id=f"{workspace_id}:{chunk_id}",
        workspace_id=workspace_id,
        source_path=source_path,
        chunk_index=0,
        content=content,
        token_estimate=len(content.split()),
        metadata={"detected_type": "markdown", "extension": ".md"},
    )


def test_sqlite_vector_store_persists_chunks_after_reinitialization(tmp_path):
    db_path = tmp_path / "nested" / "vector_store.db"
    workspace_id = "workspace-1"

    first_store = SQLiteVectorStore(db_path)
    first_store.upsert_chunks(
        workspace_id=workspace_id,
        chunks=[_chunk(workspace_id, "0", "AI Private Workspace local README")],
        embeddings=[[1.0, 0.0, 0.0]],
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=3,
    )

    second_store = SQLiteVectorStore(db_path)
    results = second_store.search(
        workspace_id=workspace_id,
        query_embedding=[1.0, 0.0, 0.0],
        limit=3,
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=3,
    )

    assert db_path.exists()
    assert len(results) == 1
    assert results[0].source_path == "README.md"
    assert "local README" in results[0].content


def test_sqlite_vector_store_reindex_replaces_without_duplicates(tmp_path):
    db_path = tmp_path / "vector_store.db"
    workspace_id = "workspace-2"
    store = SQLiteVectorStore(db_path)

    store.upsert_chunks(
        workspace_id=workspace_id,
        chunks=[_chunk(workspace_id, "0", "old content")],
        embeddings=[[1.0, 0.0]],
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=2,
    )
    store.upsert_chunks(
        workspace_id=workspace_id,
        chunks=[_chunk(workspace_id, "0", "new content")],
        embeddings=[[1.0, 0.0]],
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=2,
    )

    results = store.search(
        workspace_id=workspace_id,
        query_embedding=[1.0, 0.0],
        limit=10,
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=2,
    )

    assert len(results) == 1
    assert results[0].content == "new content"


def test_sqlite_vector_store_clear_workspace_removes_persisted_chunks(tmp_path):
    db_path = tmp_path / "vector_store.db"
    workspace_id = "workspace-3"
    store = SQLiteVectorStore(db_path)
    store.upsert_chunks(
        workspace_id=workspace_id,
        chunks=[_chunk(workspace_id, "0", "content")],
        embeddings=[[1.0]],
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=1,
    )

    store.clear_workspace(workspace_id)
    restarted_store = SQLiteVectorStore(db_path)

    assert restarted_store.search(workspace_id, [1.0], 5, "fake", "fake-embedding", 1) == []


def test_memory_vector_store_remains_temporary_provider():
    workspace_id = "workspace-memory"
    store = InMemoryVectorStore()
    store.upsert_chunks(
        workspace_id=workspace_id,
        chunks=[_chunk(workspace_id, "0", "temporary content")],
        embeddings=[[1.0]],
        embedding_provider="fake",
        embedding_model="fake-embedding",
        embedding_dimension=1,
    )

    restarted_store = InMemoryVectorStore()

    assert restarted_store.search(workspace_id, [1.0], 5, "fake", "fake-embedding", 1) == []
