"""WAL-tuned SQLite connections: readers don't block on a live writer."""

import sqlite3

from app.adapters.memory.sqlite_connection import open_sqlite


def test_wal_and_synchronous_applied(tmp_path):
    conn = open_sqlite(tmp_path / "a.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    # synchronous NORMAL == 1
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
    conn.close()


def test_creates_missing_parent_directories(tmp_path):
    # A nested path whose folders don't exist yet must not raise
    # "unable to open database file" — open_sqlite creates the parent.
    conn = open_sqlite(tmp_path / "app-owned" / "data" / "workspaces.db")
    conn.execute("CREATE TABLE t(x)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    conn.close()


def test_wal_persists_for_later_plain_connections(tmp_path):
    path = tmp_path / "b.db"
    first = open_sqlite(path)
    first.execute("CREATE TABLE t(x)")
    first.commit()
    first.close()
    # WAL is stored in the file header, so even a default connection sees it.
    plain = sqlite3.connect(path)
    assert plain.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    plain.close()


def test_reader_not_blocked_by_open_writer(tmp_path):
    """The bug this fixes: background indexing writes while /ask reads.

    Under WAL a reader can proceed against the last committed snapshot even
    while another connection holds an open write transaction — no
    'database is locked'.
    """
    path = tmp_path / "c.db"
    setup = open_sqlite(path)
    setup.execute("CREATE TABLE chunks(id INTEGER, body TEXT)")
    setup.execute("INSERT INTO chunks VALUES (1, 'hello')")
    setup.commit()
    setup.close()

    writer = open_sqlite(path)
    reader = open_sqlite(path)
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("INSERT INTO chunks VALUES (2, 'world')")
        # Reader sees the committed snapshot (1 row) without raising.
        rows = reader.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        assert rows == 1
        writer.commit()
    finally:
        writer.close()
        reader.close()
