from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from math import sqrt
from pathlib import Path
from typing import Any

from app.core.domain.indexing import ContextSearchResult, TextChunk


class SQLiteVectorStore:
    """Small app-owned persistent vector store for packaged/local RAG smoke.

    This is intentionally simple: embeddings are persisted as JSON in SQLite so
    the packaged .app can retrieve chunks after backend restart without requiring
    a separate Qdrant runtime. Qdrant remains available as the advanced provider.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path).expanduser()
        self._initialize_schema()

    def upsert_chunks(
        self,
        workspace_id: str,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return

        now = datetime.now(UTC).isoformat()
        rows = [
            (
                workspace_id,
                chunk.id,
                chunk.source_path,
                chunk.chunk_index,
                chunk.content,
                chunk.token_estimate,
                json.dumps(chunk.metadata, sort_keys=True),
                json.dumps([float(value) for value in embedding]),
                embedding_provider or "",
                embedding_model or "",
                embedding_dimension or len(embedding),
                now,
                now,
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO workspace_vector_chunks (
                    workspace_id, chunk_id, source_path, chunk_index, content,
                    token_estimate, metadata_json, embedding_json,
                    embedding_provider, embedding_model, embedding_dimension,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id, chunk_id) DO UPDATE SET
                    source_path = excluded.source_path,
                    chunk_index = excluded.chunk_index,
                    content = excluded.content,
                    token_estimate = excluded.token_estimate,
                    metadata_json = excluded.metadata_json,
                    embedding_json = excluded.embedding_json,
                    embedding_provider = excluded.embedding_provider,
                    embedding_model = excluded.embedding_model,
                    embedding_dimension = excluded.embedding_dimension,
                    updated_at = excluded.updated_at
                """,
                rows,
            )

    def search(
        self,
        workspace_id: str,
        query_embedding: list[float],
        limit: int,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> list[ContextSearchResult]:
        if limit <= 0:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id, source_path, content, metadata_json, embedding_json
                FROM workspace_vector_chunks
                WHERE workspace_id = ?
                  AND (? = '' OR embedding_provider = ?)
                  AND (? = '' OR embedding_model = ?)
                  AND (? IS NULL OR embedding_dimension = ?)
                """,
                (
                    workspace_id,
                    embedding_provider or "",
                    embedding_provider or "",
                    embedding_model or "",
                    embedding_model or "",
                    embedding_dimension,
                    embedding_dimension,
                ),
            ).fetchall()

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            embedding = self._loads_embedding(row["embedding_json"])
            scored.append((self._cosine_similarity(query_embedding, embedding), row))
        scored.sort(key=lambda item: item[0], reverse=True)

        return [
            ContextSearchResult(
                chunk_id=row["chunk_id"],
                source_path=row["source_path"],
                content=row["content"],
                score=score,
                metadata=self._loads_metadata(row["metadata_json"]),
            )
            for score, row in scored[:limit]
        ]

    def clear_workspace(
        self,
        workspace_id: str,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM workspace_vector_chunks WHERE workspace_id = ?",
                (workspace_id,),
            )

    def _initialize_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_vector_chunks (
                    workspace_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    embedding_provider TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dimension INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (workspace_id, chunk_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workspace_vector_chunks_workspace
                ON workspace_vector_chunks(workspace_id)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workspace_vector_chunks_embedding
                ON workspace_vector_chunks(workspace_id, embedding_provider, embedding_model, embedding_dimension)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _loads_embedding(value: str) -> list[float]:
        loaded = json.loads(value)
        if not isinstance(loaded, list):
            return []
        return [float(item) for item in loaded]

    @staticmethod
    def _loads_metadata(value: str) -> dict[str, str]:
        loaded: Any = json.loads(value)
        if not isinstance(loaded, dict):
            return {}
        return {str(key): str(item) for key, item in loaded.items()}

    @staticmethod
    def _cosine_similarity(first: list[float], second: list[float]) -> float:
        if not first or not second:
            return 0.0
        dimensions = min(len(first), len(second))
        dot_product = sum(first[index] * second[index] for index in range(dimensions))
        first_norm = sqrt(sum(value * value for value in first))
        second_norm = sqrt(sum(value * value for value in second))
        if first_norm == 0.0 or second_norm == 0.0:
            return 0.0
        return dot_product / (first_norm * second_norm)
