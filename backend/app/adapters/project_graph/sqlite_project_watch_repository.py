from app.adapters.memory.sqlite_connection import open_sqlite
"""SQLite-backed store for the latest Project Watcher digest per workspace,
plus an append-only change-history timeline."""

import json
import sqlite3
import uuid
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
        connection = open_sqlite(self.db_path)
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_watch_history (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    entry_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_project_watch_history_ws
                ON project_watch_history (workspace_id, created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_watch_history_cursor (
                    workspace_id TEXT PRIMARY KEY,
                    head TEXT,
                    updated_at TEXT NOT NULL
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
            connection.execute(
                "DELETE FROM project_watch_history WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.execute(
                "DELETE FROM project_watch_history_cursor WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.commit()

    def get_history_cursor(self, workspace_id: str) -> str | None:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT head FROM project_watch_history_cursor WHERE workspace_id = ?",
                (workspace_id,),
            )
            row = cursor.fetchone()
        return row["head"] if row is not None else None

    def set_history_cursor(self, workspace_id: str, head: str | None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_watch_history_cursor (workspace_id, head, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    head = excluded.head,
                    updated_at = excluded.updated_at
                """,
                (workspace_id, head, _utc_now_iso()),
            )
            connection.commit()

    def append_history(self, workspace_id: str, entry: dict) -> str:
        entry_id = str(uuid.uuid4())
        created_at = _utc_now_iso()
        record = {**dict(entry), "id": entry_id, "created_at": created_at}
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_watch_history (id, workspace_id, created_at, entry_json)
                VALUES (?, ?, ?, ?)
                """,
                (entry_id, workspace_id, created_at, json.dumps(record)),
            )
            connection.commit()
        return entry_id

    def list_history(self, workspace_id: str, limit: int = 50) -> list[dict]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT entry_json FROM project_watch_history
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (workspace_id, max(0, limit)),
            )
            rows = cursor.fetchall()
        return [json.loads(row["entry_json"]) for row in rows]

    def set_latest_history_summary(self, workspace_id: str, summary: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT id, entry_json FROM project_watch_history
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workspace_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return
            record = json.loads(row["entry_json"])
            record["llm_summary"] = summary
            connection.execute(
                "UPDATE project_watch_history SET entry_json = ? WHERE id = ?",
                (json.dumps(record), row["id"]),
            )
            connection.commit()
