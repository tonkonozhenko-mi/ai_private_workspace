from app.adapters.memory.sqlite_connection import open_sqlite
"""SQLite-backed app preferences store (global — one blob per install)."""

import json
import sqlite3
from pathlib import Path


class SQLiteAppPreferencesRepository:
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
                CREATE TABLE IF NOT EXISTS app_preferences (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    data TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def get(self) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT data FROM app_preferences WHERE id = 1").fetchone()
        if row is None:
            return None
        try:
            parsed = json.loads(row["data"])
        except (ValueError, TypeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def save(self, values: dict) -> dict:
        payload = json.dumps(values)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO app_preferences (id, data) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET data = excluded.data
                """,
                (payload,),
            )
            connection.commit()
        return dict(values)
