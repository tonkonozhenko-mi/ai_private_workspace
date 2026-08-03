"""SQLite-backed Project Group store.

Members are stored as a JSON array in a single column — groups are small and read
whole, so a join table would add ceremony without benefit. Member workspaces live
in their own table and are never touched here.
"""

import json
import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.core.domain.project_group import ProjectGroup


class SQLiteProjectGroupRepository:
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
                CREATE TABLE IF NOT EXISTS project_groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    workspace_ids TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    @staticmethod
    def _row_to_group(row: sqlite3.Row) -> ProjectGroup:
        try:
            members = tuple(json.loads(row["workspace_ids"]) or [])
        except (TypeError, ValueError):
            members = ()
        return ProjectGroup(
            id=row["id"],
            name=row["name"],
            workspace_ids=members,
            created_at=row["created_at"],
        )

    def add(self, group: ProjectGroup) -> ProjectGroup:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO project_groups (id, name, workspace_ids, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    group.id,
                    group.name,
                    json.dumps(list(group.workspace_ids)),
                    group.created_at,
                ),
            )
            connection.commit()
        return group

    def get(self, group_id: str) -> ProjectGroup | None:
        with self._connect() as connection:
            cursor = connection.execute("SELECT * FROM project_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            return self._row_to_group(row) if row else None

    def list(self) -> list[ProjectGroup]:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT * FROM project_groups ORDER BY created_at DESC, rowid DESC"
            )
            return [self._row_to_group(r) for r in cursor.fetchall()]

    def update(self, group: ProjectGroup) -> ProjectGroup:
        with self._connect() as connection:
            connection.execute(
                "UPDATE project_groups SET name = ?, workspace_ids = ? WHERE id = ?",
                (group.name, json.dumps(list(group.workspace_ids)), group.id),
            )
            connection.commit()
        return group

    def delete(self, group_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM project_groups WHERE id = ?", (group_id,))
            connection.commit()
