import sqlite3
from pathlib import Path


def open_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection tuned for concurrent local use.

    The app writes to the same database files from a background indexing thread
    while foreground requests (an ``/ask`` query, a status poll) read them. With
    SQLite's default rollback journal and a zero busy-timeout, a reader that
    arrives mid-write fails immediately with ``database is locked``.

    Two settings fix that:

    * ``journal_mode=WAL`` lets one writer and many readers use the file at the
      same time without blocking each other. It is persisted in the database
      header, so setting it on every open is idempotent and cheap.
    * a busy timeout (via the ``timeout`` arg, in seconds) makes a connection
      wait for a contended lock to clear instead of erroring out.

    ``synchronous=NORMAL`` is the recommended durability level under WAL: safe
    across app crashes, and a large write speed-up over the ``FULL`` default.

    Callers that need ``sqlite3.Row`` still set ``row_factory`` themselves.
    """
    connection = sqlite3.connect(db_path, timeout=30.0)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection
