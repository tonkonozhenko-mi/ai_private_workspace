from datetime import datetime
from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.workspace import Workspace


class SQLiteWorkspaceRepository:
    def __init__(self, db_path: str | Path) -> None:
        raw_db_path = str(db_path).strip()
        if not raw_db_path:
            raise ValueError("Workspace database path must not be empty.")
        self.db_path = Path(raw_db_path).expanduser()
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            initialize_workspace_schema(self.db_path)
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError(
                f"Could not initialize workspace SQLite database at {self.db_path}: {exc}"
            ) from exc

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

    def delete(self, workspace_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM workspaces WHERE id = ?",
                (workspace_id,),
            )
            connection.commit()
            return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.db_path)
        except (OSError, sqlite3.Error) as exc:
            raise RuntimeError(
                f"Could not open workspace SQLite database at {self.db_path}: {exc}"
            ) from exc
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
