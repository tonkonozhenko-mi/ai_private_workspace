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
            connection.commit()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            workspace_id=row["workspace_id"],
            kind=row["kind"],
            text=row["text"],
            source=row["source"],
            created_at=row["created_at"],
            pinned=bool(row["pinned"]),
        )

    def add(self, item: MemoryItem) -> MemoryItem:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO project_memory (id, workspace_id, kind, text, source, created_at, pinned)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.workspace_id,
                    item.kind,
                    item.text,
                    item.source,
                    item.created_at,
                    1 if item.pinned else 0,
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

    def clear(self, workspace_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM project_memory WHERE workspace_id = ?", (workspace_id,))
            connection.commit()
