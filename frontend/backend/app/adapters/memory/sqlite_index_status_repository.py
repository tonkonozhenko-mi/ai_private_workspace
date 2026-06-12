from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.index_status import WorkspaceIndexStatus


class SQLiteIndexStatusRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save(self, status: WorkspaceIndexStatus) -> WorkspaceIndexStatus:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_index_status (
                    workspace_id,
                    status,
                    indexed_files_count,
                    chunks_count,
                    skipped_files_count,
                    last_indexed_at,
                    last_error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    status = excluded.status,
                    indexed_files_count = excluded.indexed_files_count,
                    chunks_count = excluded.chunks_count,
                    skipped_files_count = excluded.skipped_files_count,
                    last_indexed_at = excluded.last_indexed_at,
                    last_error = excluded.last_error
                """,
                (
                    status.workspace_id,
                    status.status,
                    status.indexed_files_count,
                    status.chunks_count,
                    status.skipped_files_count,
                    status.last_indexed_at,
                    status.last_error,
                ),
            )
            connection.commit()
        return status

    def get(self, workspace_id: str) -> WorkspaceIndexStatus | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    workspace_id,
                    status,
                    indexed_files_count,
                    chunks_count,
                    skipped_files_count,
                    last_indexed_at,
                    last_error
                FROM workspace_index_status
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            return None
        return WorkspaceIndexStatus(
            workspace_id=row["workspace_id"],
            status=row["status"],
            indexed_files_count=row["indexed_files_count"],
            chunks_count=row["chunks_count"],
            skipped_files_count=row["skipped_files_count"],
            last_indexed_at=row["last_indexed_at"],
            last_error=row["last_error"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
