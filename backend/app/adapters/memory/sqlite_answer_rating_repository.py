"""SQLite-backed answer-rating store."""

import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.core.domain.answer_rating import AnswerRating


class SQLiteAnswerRatingRepository:
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
                CREATE TABLE IF NOT EXISTS answer_ratings (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    llm_model TEXT NOT NULL DEFAULT '',
                    context_chunks INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_answer_ratings_ws "
                "ON answer_ratings (workspace_id, created_at)"
            )
            connection.commit()

    @staticmethod
    def _row(row: sqlite3.Row) -> AnswerRating:
        return AnswerRating(
            id=row["id"],
            workspace_id=row["workspace_id"],
            verdict=row["verdict"],
            llm_model=row["llm_model"],
            context_chunks=int(row["context_chunks"]),
            created_at=row["created_at"],
        )

    def add(self, rating: AnswerRating) -> AnswerRating:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO answer_ratings "
                "(id, workspace_id, verdict, llm_model, context_chunks, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    rating.id,
                    rating.workspace_id,
                    rating.verdict,
                    rating.llm_model,
                    rating.context_chunks,
                    rating.created_at,
                ),
            )
            connection.commit()
        return rating

    def list(self, workspace_id: str, limit: int = 50) -> list[AnswerRating]:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT * FROM answer_ratings WHERE workspace_id = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (workspace_id, limit),
            )
            return [self._row(r) for r in cursor.fetchall()]
