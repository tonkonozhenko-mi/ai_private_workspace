from datetime import datetime
from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.workspace import Workspace


class SQLiteWorkspaceRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def create(self, workspace: Workspace) -> Workspace:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspaces (
                    id,
                    name,
                    project_path,
                    assistant_mode,
                    privacy_mode,
                    created_at,
                    archived_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace.id,
                    workspace.name,
                    workspace.project_path,
                    workspace.assistant_mode,
                    workspace.privacy_mode,
                    workspace.created_at.isoformat(),
                    workspace.archived_at,
                ),
            )
            connection.commit()
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    name,
                    project_path,
                    assistant_mode,
                    privacy_mode,
                    created_at,
                    archived_at
                FROM workspaces
                WHERE id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            return None
        return self._to_workspace(row)

    def list(self) -> list[Workspace]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    name,
                    project_path,
                    assistant_mode,
                    privacy_mode,
                    created_at,
                    archived_at
                FROM workspaces
                ORDER BY created_at ASC
                """
            ).fetchall()

        return [self._to_workspace(row) for row in rows]

    def update(self, workspace: Workspace) -> Workspace:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE workspaces
                SET
                    name = ?,
                    project_path = ?,
                    assistant_mode = ?,
                    privacy_mode = ?,
                    created_at = ?,
                    archived_at = ?
                WHERE id = ?
                """,
                (
                    workspace.name,
                    workspace.project_path,
                    workspace.assistant_mode,
                    workspace.privacy_mode,
                    workspace.created_at.isoformat(),
                    workspace.archived_at,
                    workspace.id,
                ),
            )
            connection.commit()
        return workspace

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_workspace(row: sqlite3.Row) -> Workspace:
        return Workspace(
            id=row["id"],
            name=row["name"],
            project_path=row["project_path"],
            assistant_mode=row["assistant_mode"],
            privacy_mode=row["privacy_mode"],
            created_at=datetime.fromisoformat(row["created_at"]),
            archived_at=row["archived_at"],
        )
