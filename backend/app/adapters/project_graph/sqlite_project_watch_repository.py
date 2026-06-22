"""SQLite-backed store for the latest Project Watcher digest per workspace."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteProjectWatchRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_watch_digests (
                    workspace_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    digest_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def save_digest(self, workspace_id: str, digest: dict) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_watch_digests (workspace_id, created_at, digest_json)
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    digest_json = excluded.digest_json
                """,
                (workspace_id, _utc_now_iso(), json.dumps(digest)),
            )
            connection.commit()

    def get_latest_digest(self, workspace_id: str) -> dict | None:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT digest_json FROM project_watch_digests WHERE workspace_id = ?",
                (workspace_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return json.loads(row["digest_json"])

    def clear(self, workspace_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM project_watch_digests WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.commit()
