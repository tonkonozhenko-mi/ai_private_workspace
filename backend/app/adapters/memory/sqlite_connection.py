import sqlite3
from pathlib import Path


def open_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection tuned for concurrent local use.

    The app opens a fresh connection per repository operation and writes to the
    same database files from a background indexing thread while foreground
    requests read them. With SQLite's default zero busy-timeout, a reader that
    arrives mid-write fails immediately with ``database is locked``.

    ``timeout=30`` gives every connection a busy-timeout so a contended lock is
    waited on instead of erroring — this is the actual fix, and it needs no
    on-disk side files.

    WAL journal mode is deliberately *not* enabled here. It would let readers
    and a writer share the file, but it also opens three file handles per
    connection (``.db`` + ``-wal`` + ``-shm``) instead of one. Because the app
    opens many short-lived connections, that triples file-descriptor pressure
    and can exhaust the process's open-file limit under load
    (``sqlite3.OperationalError: unable to open database file``). The default
    rollback journal keeps one handle per connection and is plenty for a
    local-first app.

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

    return sqlite3.connect(db_path, timeout=30.0)
