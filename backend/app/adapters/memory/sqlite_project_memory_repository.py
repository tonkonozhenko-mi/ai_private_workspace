"""SQLite-backed Project Memory store."""

import sqlite3
from pathlib import Path

from app.core.domain.project_memory import MemoryItem


class SQLiteProjectMemoryRepository:
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
                CREATE TABLE IF NOT EXISTS project_memory (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_memory_ws "
                "ON project_memory (workspace_id, created_at)"
            )
            # Lifecycle columns added in a later version; SQLite has no
            # 'ADD COLUMN IF NOT EXISTS', so check the table info first.
            cols = {r["name"] for r in connection.execute("PRAGMA table_info(project_memory)")}
            if "confidence" not in cols:
                connection.execute(
                    "ALTER TABLE project_memory ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0"
                )
            if "status" not in cols:
                connection.execute(
                    "ALTER TABLE project_memory ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
                )
            if "updated_at" not in cols:
                connection.execute("ALTER TABLE project_memory ADD COLUMN updated_at TEXT")
            connection.commit()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> MemoryItem:
        keys = row.keys()
        confidence = row["confidence"] if "confidence" in keys and row["confidence"] is not None else 1.0
        return MemoryItem(
            id=row["id"],
            workspace_id=row["workspace_id"],
            kind=row["kind"],
            text=row["text"],
            source=row["source"],
            created_at=row["created_at"],
            pinned=bool(row["pinned"]),
            confidence=confidence,
            status=(row["status"] if "status" in keys and row["status"] else "active"),
            updated_at=(row["updated_at"] if "updated_at" in keys else None),
        )

    def add(self, item: MemoryItem) -> MemoryItem:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_memory
                    (id, workspace_id, kind, text, source, created_at, pinned,
                     confidence, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.workspace_id,
                    item.kind,
                    item.text,
                    item.source,
                    item.created_at,
                    1 if item.pinned else 0,
                    item.confidence,
                    item.status,
                    item.updated_at,
                ),
            )
            connection.commit()
        return item

    def list(self, workspace_id: str) -> list[MemoryItem]:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT * FROM project_memory WHERE workspace_id = ? "
                "ORDER BY created_at DESC, rowid DESC",
                (workspace_id,),
            )
            return [self._row_to_item(r) for r in cursor.fetchall()]

    def delete(self, workspace_id: str, item_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM project_memory WHERE workspace_id = ? AND id = ?",
                (workspace_id, item_id),
            )
            connection.commit()

    def delete_kind(self, workspace_id: str, kind: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM project_memory WHERE workspace_id = ? AND kind = ?",
                (workspace_id, kind),
            )
            connection.commit()

    def set_pinned(self, workspace_id: str, item_id: str, pinned: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE project_memory SET pinned = ? WHERE workspace_id = ? AND id = ?",
                (1 if pinned else 0, workspace_id, item_id),
            )
            connection.commit()

    def set_status(self, workspace_id: str, item_id: str, status: str) -> None:
        from datetime import datetime, timezone

        with self._connect() as connection:
            connection.execute(
                "UPDATE project_memory SET status = ?, updated_at = ? "
                "WHERE workspace_id = ? AND id = ?",
                (status, datetime.now(timezone.utc).isoformat(), workspace_id, item_id),
            )
            connection.commit()

    def clear(self, workspace_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM project_memory WHERE workspace_id = ?", (workspace_id,))
            connection.commit()
