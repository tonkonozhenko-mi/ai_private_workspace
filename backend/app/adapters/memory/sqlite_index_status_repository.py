import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.index_status import WorkspaceIndexStatus


class SQLiteIndexStatusRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)
        self._ensure_embedding_model_column()

    def _ensure_embedding_model_column(self) -> None:
        """Add the embedding_model column to pre-existing databases. SQLite has no
        'ADD COLUMN IF NOT EXISTS', so check the table info first."""
        with self._connect() as connection:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(workspace_index_status)")
            }
            if "embedding_model" not in columns:
                connection.execute(
                    "ALTER TABLE workspace_index_status ADD COLUMN embedding_model TEXT"
                )
                connection.commit()

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
                    last_error,
                    embedding_model
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    status = excluded.status,
                    indexed_files_count = excluded.indexed_files_count,
                    chunks_count = excluded.chunks_count,
                    skipped_files_count = excluded.skipped_files_count,
                    last_indexed_at = excluded.last_indexed_at,
                    last_error = excluded.last_error,
                    embedding_model = excluded.embedding_model
                """,
                (
                    status.workspace_id,
                    status.status,
                    status.indexed_files_count,
                    status.chunks_count,
                    status.skipped_files_count,
                    status.last_indexed_at,
                    status.last_error,
                    status.embedding_model,
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
                    last_error,
                    embedding_model
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
            embedding_model=row["embedding_model"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = open_sqlite(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
