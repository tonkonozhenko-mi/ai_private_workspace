import sqlite3
from pathlib import Path


def open_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection tuned for concurrent local use.

    The app writes to the same database files from a background indexing thread
    while foreground requests (an ``/ask`` query, a status poll) read them. With
    SQLite's default zero busy-timeout, a reader that arrives mid-write fails
    immediately with ``database is locked``.

    Robustness matters more than the optimisation here, so this is deliberately
    defensive:

    * the parent directory is created if missing (some callers pass a nested
      path before anything else has made the folder), guarded so a genuinely
      bad path still surfaces the real error from ``connect``;
    * ``timeout=30`` gives every connection a busy-timeout, so a contended lock
      is waited on instead of erroring — this is the actual fix for
      ``database is locked`` and needs no on-disk side files;
    * ``journal_mode=WAL`` (readers and a writer share the file) and
      ``synchronous=NORMAL`` are applied best-effort: if the filesystem can't
      support WAL's ``-wal``/``-shm`` side files the connection simply keeps the
      default journal instead of failing to open.

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
    except sqlite3.DatabaseError:
        # WAL isn't available on this filesystem/mode — the busy-timeout above
        # still applies, so the connection stays usable with the default journal.
        pass
    return connection
