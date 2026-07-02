"""Batched (numpy) dense scoring must match the exact scalar cosine."""

import json
import random

import app.adapters.vector_store.sqlite_vector_store as vs_module
from app.adapters.vector_store.sqlite_vector_store import SQLiteVectorStore
from app.core.domain.indexing import TextChunk


def _rows(count, dim, seed=0):
    rng = random.Random(seed)
    return [{"embedding_json": json.dumps([rng.random() for _ in range(dim)])} for _ in range(count)]


def test_numpy_matches_pure_python_exactly(tmp_path):
    store = SQLiteVectorStore(tmp_path / "v.db")
    rng = random.Random(1)
    query = [rng.random() for _ in range(48)]
    rows = _rows(count=250, dim=48, seed=2)

    assert vs_module._np is not None, "numpy expected available in this env"
    numpy_scores = store._dense_scores(query, rows)

    original = vs_module._np
    vs_module._np = None  # force the pure-Python path
    try:
        python_scores = store._dense_scores(query, rows)
    finally:
        vs_module._np = original

    assert len(numpy_scores) == len(python_scores) == len(rows)
    for (num_score, num_row), (py_score, py_row) in zip(numpy_scores, python_scores):
        assert num_row is py_row  # order preserved (stable tie-breaking)
        assert abs(num_score - py_score) < 1e-9


def test_zero_query_scores_zero(tmp_path):
    store = SQLiteVectorStore(tmp_path / "v.db")
    rows = _rows(count=5, dim=16, seed=3)
    assert all(score == 0.0 for score, _ in store._dense_scores([0.0] * 16, rows))


def test_search_ranks_the_closest_chunk_first(tmp_path):
    store = SQLiteVectorStore(tmp_path / "v.db")
    chunks = [
        TextChunk("c1", "w", "a.txt", 0, "alpha", 1, {}),
        TextChunk("c2", "w", "b.txt", 0, "beta", 1, {}),
        TextChunk("c3", "w", "c.txt", 0, "gamma", 1, {}),
    ]
    embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]]
    store.upsert_chunks("w", chunks, embeddings)

    results = store.search("w", [1.0, 0.0, 0.0], limit=3, query_text=None)
    assert results[0].chunk_id == "c1"  # exact match ranks first
    assert {r.chunk_id for r in results} == {"c1", "c2", "c3"}
