import json
import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.timeline import TimelineEvent


class SQLiteTimelineRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def add(self, event: TimelineEvent) -> TimelineEvent:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_timeline_events (
                    id,
                    workspace_id,
                    event_type,
                    title,
                    summary,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.workspace_id,
                    event.event_type,
                    event.title,
                    event.summary,
                    json.dumps(event.metadata, sort_keys=True),
                    event.created_at,
                ),
            )
            connection.commit()
        return event

    def list_by_workspace(
        self,
        workspace_id: str,
        limit: int = 50,
    ) -> list[TimelineEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    workspace_id,
                    event_type,
                    title,
                    summary,
                    metadata_json,
                    created_at
                FROM workspace_timeline_events
                WHERE workspace_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (workspace_id, max(0, limit)),
            ).fetchall()

        return [
            TimelineEvent(
                id=row["id"],
                workspace_id=row["workspace_id"],
                event_type=row["event_type"],
                title=row["title"],
                summary=row["summary"],
                metadata=json.loads(row["metadata_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
