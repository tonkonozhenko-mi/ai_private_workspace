"""A damaged index surfaces a typed error, not a raw sqlite3 500."""

import sqlite3

import pytest

from app.adapters.vector_store.sqlite_vector_store import (
    SQLiteVectorStore,
    _raise_if_corrupt,
)
from app.core.ports.vector_store import VectorStoreCorruptError


def test_raise_if_corrupt_translates_only_corruption():
    # Real corruption markers → typed error.
    for message in (
        "database disk image is malformed",
        "file is not a database",
        "file is encrypted or is not a database",
    ):
        with pytest.raises(VectorStoreCorruptError):
            _raise_if_corrupt(sqlite3.DatabaseError(message))
    # An ordinary operational error is left for the caller to re-raise.
    assert _raise_if_corrupt(sqlite3.DatabaseError("no such table: foo")) is None


def test_search_on_corrupt_index_raises_typed_error(tmp_path):
    path = tmp_path / "vector_store.db"
    store = SQLiteVectorStore(path)  # creates a valid, empty index

    # Simulate on-disk corruption: wipe WAL side-files and clobber the header.
    for suffix in ("", "-wal", "-shm"):
        p = tmp_path / f"vector_store.db{suffix}"
        if p.exists():
            p.unlink()
    path.write_bytes(b"not a sqlite database, just garbage bytes " * 64)

    with pytest.raises(VectorStoreCorruptError):
        store.search("w", [0.1, 0.2, 0.3], limit=5, query_text="anything")


def test_search_on_healthy_empty_index_returns_empty(tmp_path):
    store = SQLiteVectorStore(tmp_path / "vector_store.db")
    assert store.search("w", [0.1, 0.2, 0.3], limit=5, query_text="anything") == []
