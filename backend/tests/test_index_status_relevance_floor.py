"""The calibrated relevance floor round-trips through the SQLite index-status store,
and older databases (no column yet) migrate and read back None."""

import sqlite3

from app.adapters.memory.sqlite_index_status_repository import SQLiteIndexStatusRepository
from app.core.domain.index_status import WorkspaceIndexStatus


def _status(workspace_id: str, floor: float | None) -> WorkspaceIndexStatus:
    return WorkspaceIndexStatus(
        workspace_id=workspace_id,
        status="indexed",
        indexed_files_count=3,
        chunks_count=42,
        skipped_files_count=0,
        last_indexed_at="2026-07-03T00:00:00+00:00",
        last_error=None,
        embedding_model="nomic-embed-text",
        relevance_floor=floor,
    )


def test_relevance_floor_round_trips(tmp_path):
    repo = SQLiteIndexStatusRepository(tmp_path / "w.db")
    repo.save(_status("ws1", 0.27))
    got = repo.get("ws1")
    assert got is not None
    assert got.relevance_floor == 0.27
    assert got.embedding_model == "nomic-embed-text"


def test_relevance_floor_none_persists_as_none(tmp_path):
    repo = SQLiteIndexStatusRepository(tmp_path / "w.db")
    repo.save(_status("ws2", None))
    got = repo.get("ws2")
    assert got is not None
    assert got.relevance_floor is None


def test_migration_adds_column_to_preexisting_db(tmp_path):
    # Simulate a database created before the column existed: build the base table
    # by hand without relevance_floor, then open the repo (which migrates it).
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE workspace_index_status (
            workspace_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            indexed_files_count INTEGER NOT NULL,
            chunks_count INTEGER NOT NULL,
            skipped_files_count INTEGER NOT NULL,
            last_indexed_at TEXT NULL,
            last_error TEXT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO workspace_index_status VALUES ('old', 'indexed', 1, 2, 0, NULL, NULL)"
    )
    conn.commit()
    conn.close()

    repo = SQLiteIndexStatusRepository(db)  # migrates: adds embedding_model + relevance_floor
    got = repo.get("old")
    assert got is not None
    assert got.relevance_floor is None  # legacy row → no calibrated floor yet
    # And a fresh save with a floor works on the migrated table.
    repo.save(_status("old", 0.33))
    assert repo.get("old").relevance_floor == 0.33
