import sqlite3
from pathlib import Path


def open_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection tuned for concurrent local use.

    The app opens a fresh connection per repository operation and writes to the
    same database files from a background indexing thread while foreground
    requests read them. Three settings make that safe and fast on any machine,
    including low-end laptops with slow disks:

    - ``timeout=30`` / ``busy_timeout``: a reader that arrives mid-write waits
      for the lock instead of failing instantly with ``database is locked``.
    - ``journal_mode=WAL``: readers and the writer share the file without
      blocking each other — Ask stays responsive while a long "Build search
      context" writes thousands of chunks. WAL is persistent per database, so
      re-issuing the pragma on connect is effectively free.
    - ``synchronous=NORMAL``: in WAL mode this skips a per-commit fsync while
      remaining crash-safe (the WAL is synced at checkpoints). On slow spinning
      or throttled disks this is the difference between an index build that
      crawls and one that finishes.

    History: WAL was previously avoided here because it holds three file
    handles per connection (``.db`` + ``-wal`` + ``-shm``) and macOS gives
    GUI-launched processes only 256 descriptors — under connection-per-
    operation churn that ceiling was reachable. The backend now raises its
    RLIMIT_NOFILE at startup (see ``app/config/fd_limit.py``), which removes
    that constraint; the pragmas below are wrapped defensively anyway, so a
    filesystem that rejects WAL (some network mounts) just falls back to the
    rollback journal instead of failing the operation.

    The parent directory is created if missing (some callers pass a nested path
    before anything else has made the folder), guarded so a genuinely bad path
    still surfaces the real error from ``connect``.

    Callers that need ``sqlite3.Row`` still set ``row_factory`` themselves.
    """
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Let sqlite3.connect surface the real problem (e.g. a parent that is a
        # file, or a path we're not allowed to create).
        pass

    connection = sqlite3.connect(db_path, timeout=30.0)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=30000")
    except sqlite3.DatabaseError:
        # Pragmas are an optimization, never a requirement: fall back to the
        # defaults rather than failing the caller's operation (e.g. WAL being
        # rejected on a network filesystem, or a corrupt DB that the caller's
        # own error handling is about to deal with).
        pass
    return connection
