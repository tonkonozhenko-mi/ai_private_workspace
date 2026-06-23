"""SQLite-backed User Profile store (global — one profile per install)."""

import sqlite3
from pathlib import Path

from app.core.domain.user_profile import UserProfileItem


class SQLiteUserProfileRepository:
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
                CREATE TABLE IF NOT EXISTS user_profile (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.commit()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> UserProfileItem:
        return UserProfileItem(
            id=row["id"],
            category=row["category"],
            text=row["text"],
            created_at=row["created_at"],
            pinned=bool(row["pinned"]),
        )

    def add(self, item: UserProfileItem) -> UserProfileItem:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_profile (id, category, text, created_at, pinned)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item.id, item.category, item.text, item.created_at, 1 if item.pinned else 0),
            )
            connection.commit()
        return item

    def list(self) -> list[UserProfileItem]:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT * FROM user_profile ORDER BY created_at DESC, rowid DESC"
            )
            return [self._row_to_item(r) for r in cursor.fetchall()]

    def delete(self, item_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM user_profile WHERE id = ?", (item_id,))
            connection.commit()

    def set_pinned(self, item_id: str, pinned: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE user_profile SET pinned = ? WHERE id = ?",
                (1 if pinned else 0, item_id),
            )
            connection.commit()

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM user_profile")
            connection.commit()
