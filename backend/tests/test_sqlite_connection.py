"""Tuned SQLite connections: busy-timeout for contention, no FD-hungry WAL."""

from app.adapters.memory.sqlite_connection import open_sqlite


def test_connection_is_usable(tmp_path):
    conn = open_sqlite(tmp_path / "a.db")
    conn.execute("CREATE TABLE t(x)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    conn.close()


def test_does_not_enable_wal(tmp_path):
    # WAL is intentionally off: it opens -wal/-shm side files (3 handles per
    # connection) and the app opens many connections, which exhausts the
    # open-file limit. The default rollback journal keeps one handle.
    conn = open_sqlite(tmp_path / "a.db")
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] != "wal"
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


def test_many_short_lived_connections_do_not_exhaust_handles(tmp_path):
    # Mirrors the app's connection-per-operation pattern: opening a lot of
    # connections to the same file must not run out of file descriptors.
    path = tmp_path / "busy.db"
    open_sqlite(path).execute("CREATE TABLE t(x)")
    for i in range(500):
        conn = open_sqlite(path)
        conn.execute("INSERT INTO t VALUES (?)", (i,))
        conn.commit()
        conn.close()
    conn = open_sqlite(path)
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 500
    conn.close()
