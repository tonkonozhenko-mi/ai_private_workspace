"""Tuned SQLite connections: WAL + busy-timeout so Ask stays responsive while
a long index build writes, on any hardware.

WAL was previously avoided because of file-descriptor pressure under macOS's
256-descriptor GUI default; the backend now raises RLIMIT_NOFILE at startup
(app/config/fd_limit.py), so WAL's concurrency wins are safe to take.
"""

import sqlite3
import threading

from app.adapters.memory.sqlite_connection import open_sqlite


def test_connection_is_usable(tmp_path):
    conn = open_sqlite(tmp_path / "a.db")
    conn.execute("CREATE TABLE t(x)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1
    conn.close()


def test_enables_wal_and_tuned_pragmas(tmp_path):
    conn = open_sqlite(tmp_path / "a.db")
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    # NORMAL == 1; keeps commits cheap on slow disks while staying crash-safe in WAL.
    assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    conn.close()


def test_reader_not_blocked_during_write_transaction(tmp_path):
    """The low-end-hardware scenario WAL exists for: a long write transaction
    (index build) must not block a concurrent reader (Ask)."""
    path = tmp_path / "concurrent.db"
    setup = open_sqlite(path)
    setup.execute("CREATE TABLE t(x)")
    setup.execute("INSERT INTO t VALUES (0)")
    setup.commit()
    setup.close()

    writer = open_sqlite(path)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO t VALUES (1)")
    # Transaction intentionally left open — the writer holds the write lock.

    result: list[int] = []
    error: list[BaseException] = []

    def read() -> None:
        try:
            reader = open_sqlite(path)
            # Snapshot isolation: sees committed state, doesn't wait, doesn't fail.
            result.append(reader.execute("SELECT COUNT(*) FROM t").fetchone()[0])
            reader.close()
        except BaseException as exc:  # noqa: BLE001 - recorded for the assert
            error.append(exc)

    thread = threading.Thread(target=read)
    thread.start()
    thread.join(timeout=5)

    writer.rollback()
    writer.close()

    assert not error, f"reader failed during write transaction: {error}"
    assert result == [1]


def test_falls_back_when_pragmas_rejected(tmp_path, monkeypatch):
    """Pragmas are best-effort: a connection whose pragma fails must still be
    returned usable rather than raising at open time."""
    real_connect = sqlite3.connect

    class PragmaRejectingConnection:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, sql, *args):
            if str(sql).strip().upper().startswith("PRAGMA"):
                raise sqlite3.DatabaseError("pragma rejected")
            return self._inner.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *a, **k: PragmaRejectingConnection(real_connect(*a, **k)),
    )

    conn = open_sqlite(tmp_path / "fallback.db")
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
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
    # WAL connections to the same file must not run out of file descriptors
    # (each open connection holds .db + -wal + -shm, released on close).
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
