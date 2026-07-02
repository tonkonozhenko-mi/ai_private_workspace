"""SQLite-backed index manifest: what files are indexed and at which content hash."""

import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.core.ports.index_manifest_repository import ManifestEntry


class SQLiteIndexManifestRepository:
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
                CREATE TABLE IF NOT EXISTS workspace_index_manifest (
                    workspace_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    chunks INTEGER NOT NULL,
                    PRIMARY KEY (workspace_id, source_path)
                )
                """
            )
            connection.commit()

    def get(self, workspace_id: str) -> dict[str, ManifestEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT source_path, content_hash, chunks "
                "FROM workspace_index_manifest WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
        return {
            row["source_path"]: {"hash": row["content_hash"], "chunks": row["chunks"]}
            for row in rows
        }

    def replace_all(self, workspace_id: str, entries: dict[str, ManifestEntry]) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM workspace_index_manifest WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.executemany(
                """
                INSERT INTO workspace_index_manifest (workspace_id, source_path, content_hash, chunks)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (workspace_id, path, str(entry.get("hash", "")), int(entry.get("chunks", 0)))
                    for path, entry in entries.items()
                ],
            )
            connection.commit()

    def upsert(self, workspace_id: str, source_path: str, content_hash: str, chunks: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_index_manifest (workspace_id, source_path, content_hash, chunks)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, source_path) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    chunks = excluded.chunks
                """,
                (workspace_id, source_path, content_hash, chunks),
            )
            connection.commit()

    def delete(self, workspace_id: str, source_paths: list[str]) -> None:
        paths = [p for p in dict.fromkeys(source_paths) if p]
        if not paths:
            return
        placeholders = ",".join("?" for _ in paths)
        with self._connect() as connection:
            connection.execute(
                f"DELETE FROM workspace_index_manifest "
                f"WHERE workspace_id = ? AND source_path IN ({placeholders})",
                (workspace_id, *paths),
            )
            connection.commit()

    def clear(self, workspace_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM workspace_index_manifest WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.commit()
