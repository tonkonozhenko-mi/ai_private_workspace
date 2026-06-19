"""Hybrid (vector + BM25) retrieval contract for the SQLite vector store.

Pure vector search misses exact identifiers (folder/var names). These tests pin
the behaviour that BM25 keyword matching — fused with the vector ranking via
Reciprocal Rank Fusion — surfaces the lexically-relevant chunk that vector-only
search ranks last.
"""

from __future__ import annotations

from app.adapters.vector_store.sqlite_vector_store import SQLiteVectorStore
from app.core.domain.indexing import TextChunk


def _chunk(chunk_id: str, source_path: str, content: str) -> TextChunk:
    return TextChunk(
        id=chunk_id,
        workspace_id="w1",
        source_path=source_path,
        chunk_index=0,
        content=content,
        token_estimate=10,
        metadata={},
    )


def _seed(store: SQLiteVectorStore) -> None:
    chunks = [
        _chunk(
            "A",
            "accounts/dev/ca-central-1/myapp/application.tf",
            "resource aws_ecs_service myapp; myapp_allowed_cidr = 10.0.0.0/24",
        ),
        _chunk("B", "accounts/stg/ca-central-1/myapp/application.tf", "myapp_allowed_cidr = 172.27.103.0/24"),
        _chunk("C", "README.md", "general project documentation about deployment"),
    ]
    # C's embedding is the closest match to the query vector below.
    embeddings = [[0.0, 1.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
    store.upsert_chunks(
        "w1", chunks, embeddings, embedding_provider="p", embedding_model="m", embedding_dimension=3
    )


_QUERY = [1.0, 0.0, 0.0]


def test_pure_vector_ranks_generic_chunk_first(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vec.db")
    _seed(store)
    # Without query_text it is vector-only: the generic README wins on cosine.
    results = store.search("w1", _QUERY, 3, "p", "m", 3)
    assert results[0].chunk_id == "C"


def test_hybrid_surfaces_keyword_match(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vec.db")
    _seed(store)
    # With the question text, BM25 matches "ecs/myapp/dev" in the dev myapp file's
    # path + content and RRF lifts it above the generic vector winner.
    results = store.search(
        "w1", _QUERY, 3, "p", "m", 3, query_text="how is ecs configured for myapp in dev environment"
    )
    assert results[0].chunk_id == "A"
    assert {r.chunk_id for r in results} == {"A", "B", "C"}


def test_punctuation_in_query_does_not_break_fts(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vec.db")
    _seed(store)
    results = store.search("w1", _QUERY, 3, "p", "m", 3, query_text='ecs("myapp") in dev? (test)')
    assert len(results) == 3


def test_clear_workspace_also_clears_keyword_index(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vec.db")
    _seed(store)
    store.clear_workspace("w1")
    assert store.search("w1", _QUERY, 3, "p", "m", 3, query_text="myapp dev") == []


def test_path_boost_lifts_the_matching_environment_file(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vec.db")
    chunks = [
        _chunk("dev_ecs", "accounts/dev/ca-central-1/myapp/ecs.tf", "resource aws_ecs_service myapp"),
        _chunk(
            "datasync",
            "accounts/dev/eu-west-1/datasync/secretsmanager.tf",
            "enable_ec2_endpoint_connect = true",
        ),
    ]
    # datasync is the best vector match; only the path boost should overrule it.
    embeddings = [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
    store.upsert_chunks("w1", chunks, embeddings, embedding_provider="p", embedding_model="m", embedding_dimension=3)
    results = store.search(
        "w1", [1.0, 0.0, 0.0], 2, "p", "m", 3, query_text="how is ecs configured in myapp dev"
    )
    # The dev/myapp/ecs file (path segments dev + myapp + ecs all match) leads.
    assert results[0].chunk_id == "dev_ecs"


def test_diversity_caps_chunks_from_one_file(tmp_path) -> None:
    store = SQLiteVectorStore(tmp_path / "vec.db")
    big = [_chunk(f"big{i}", "accounts/uat/myapp/application.tf", f"myapp config {i}") for i in range(5)]
    other = [_chunk("dev", "accounts/dev/myapp/ecs.tf", "myapp config dev")]
    chunks = big + other
    embeddings = [[0.0, 1.0, 0.0]] * 5 + [[0.0, 1.0, 0.0]]
    store.upsert_chunks("w1", chunks, embeddings, embedding_provider="p", embedding_model="m", embedding_dimension=3)
    results = store.search("w1", [0.0, 1.0, 0.0], 3, "p", "m", 3, query_text="myapp config")
    paths = [r.source_path for r in results]
    # The 5-chunk file must not fill all 3 slots — the other file gets a place.
    assert "accounts/dev/myapp/ecs.tf" in paths
