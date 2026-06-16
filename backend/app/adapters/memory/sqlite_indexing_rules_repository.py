import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.indexing_rules import IndexingRulesProfile


class SQLiteIndexingRulesRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def get(self, workspace_id: str) -> IndexingRulesProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT workspace_id, profile, include_patterns_json, exclude_patterns_json, updated_at
                FROM workspace_indexing_rules
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        return IndexingRulesProfile(
            workspace_id=row["workspace_id"],
            profile=row["profile"],
            include_patterns=tuple(json.loads(row["include_patterns_json"])),
            exclude_patterns=tuple(json.loads(row["exclude_patterns_json"])),
            updated_at=row["updated_at"],
        )

    def save(self, profile: IndexingRulesProfile) -> IndexingRulesProfile:
        saved = IndexingRulesProfile(
            workspace_id=profile.workspace_id,
            profile=profile.profile,
            include_patterns=profile.include_patterns,
            exclude_patterns=profile.exclude_patterns,
            updated_at=profile.updated_at or datetime.now(UTC).isoformat(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_indexing_rules (
                    workspace_id, profile, include_patterns_json, exclude_patterns_json, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    profile = excluded.profile,
                    include_patterns_json = excluded.include_patterns_json,
                    exclude_patterns_json = excluded.exclude_patterns_json,
                    updated_at = excluded.updated_at
                """,
                (
                    saved.workspace_id,
                    saved.profile,
                    json.dumps(list(saved.include_patterns)),
                    json.dumps(list(saved.exclude_patterns)),
                    saved.updated_at,
                ),
            )
            connection.commit()
        return saved

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
