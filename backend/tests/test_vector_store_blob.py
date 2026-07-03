"""Float32-blob embedding storage: round-trip, legacy JSON compat, ranking."""

import json
import struct

from app.adapters.vector_store.sqlite_vector_store import SQLiteVectorStore
from app.core.domain.indexing import TextChunk


def _chunk(cid, path):
    return TextChunk(cid, "w", path, 0, "content", 1, {})


def test_upsert_stores_blob_and_empty_json(tmp_path):
    store = SQLiteVectorStore(tmp_path / "v.db")
    store.upsert_chunks("w", [_chunk("c1", "a.txt")], [[0.5, -0.25, 0.125]])
    with store._connect() as conn:
        row = conn.execute(
            "SELECT embedding_json, embedding_blob FROM workspace_vector_chunks "
            "WHERE chunk_id = 'c1'"
        ).fetchone()
    assert row["embedding_json"] == "[]"  # no more fat JSON vector on disk
    assert row["embedding_blob"] is not None
    # float32 round-trips exactly for these values
    decoded = list(struct.unpack(f"<{len(row['embedding_blob']) // 4}f", row["embedding_blob"]))
    assert decoded == [0.5, -0.25, 0.125]


def test_search_ranks_correctly_from_blob(tmp_path):
    store = SQLiteVectorStore(tmp_path / "v.db")
    store.upsert_chunks(
        "w",
        [_chunk("c1", "a.txt"), _chunk("c2", "b.txt"), _chunk("c3", "c.txt")],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]],
    )
    results = store.search("w", [1.0, 0.0, 0.0], limit=3, query_text=None)
    assert [r.chunk_id for r in results][0] == "c1"
    assert {r.chunk_id for r in results} == {"c1", "c2", "c3"}


def test_legacy_json_rows_still_searchable(tmp_path):
    """Rows written before blob storage (embedding_json, no blob) must still
    decode and rank — the migration is additive, not destructive."""
    store = SQLiteVectorStore(tmp_path / "v.db")
    # Simulate an old row: real JSON vector, NULL blob.
    with store._connect() as conn:
        conn.execute(
            """
            INSERT INTO workspace_vector_chunks (
                workspace_id, chunk_id, source_path, chunk_index, content,
                token_estimate, metadata_json, embedding_json, embedding_blob,
                embedding_provider, embedding_model, embedding_dimension,
                created_at, updated_at
            ) VALUES ('w','old','old.txt',0,'x',1,'{}',?,NULL,'','',3,'t','t')
            """,
            (json.dumps([1.0, 0.0, 0.0]),),
        )
        conn.commit()
    results = store.search("w", [1.0, 0.0, 0.0], limit=3, query_text=None)
    assert any(r.chunk_id == "old" for r in results)
    assert results[0].chunk_id == "old"  # exact match still wins
