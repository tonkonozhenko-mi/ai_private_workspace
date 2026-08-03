from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.workspace_storage import WorkspaceStorageBreakdown

# Category -> list of (table, workspace_id_column, [text columns to sum]).
# Sizes are approximate: we sum the byte length of the meaningful text columns
# per workspace. This is a stable proxy for "how much space this project uses".
_MAIN_DB_SOURCES: dict[str, list[tuple[str, str, list[str]]]] = {
    "index": [
        ("workspace_index_status", "workspace_id", ["last_error"]),
    ],
    "conversations": [
        ("workspace_conversations", "workspace_id", ["title"]),
        (
            "workspace_conversation_messages",
            "workspace_id",
            ["content", "sources_json", "skill_profile_json"],
        ),
    ],
    "notes": [
        (
            "workspace_answer_notes",
            "workspace_id",
            ["title", "content", "source_question", "source_paths_json"],
        ),
        (
            "workspace_saved_reports",
            "workspace_id",
            ["title", "summary", "export_markdown", "export_text", "report_json"],
        ),
    ],
    "scan": [
        ("workspace_project_scans", "workspace_id", ["scan_json"]),
    ],
    "other": [
        ("workspace_commands", "workspace_id", ["command", "reason", "stdout", "stderr"]),
        ("workspace_timeline_events", "workspace_id", ["title", "summary", "metadata_json"]),
        ("workspace_model_experiments", "workspace_id", ["run_json"]),
        ("workspace_model_selections", "workspace_id", ["selection_json"]),
        ("local_model_download_jobs", "workspace_id", ["job_json"]),
        ("workspace_skill_profiles", "workspace_id", ["skills_json"]),
        ("workspace_agent_workflows", "workspace_id", ["goal", "steps_json", "guardrails_json"]),
        ("workspace_mcp_configs", "workspace_id", ["config_json", "available_tools_json"]),
        (
            "workspace_indexing_rules",
            "workspace_id",
            ["include_patterns_json", "exclude_patterns_json"],
        ),
    ],
}

# Tables to wipe on hard delete (main DB). Order is not significant - all rows
# are matched by workspace_id. workspace_model_experiment_ratings is keyed by
# experiment_id and handled separately.
_MAIN_DB_DELETE_TABLES: list[str] = [
    "workspace_project_scans",
    "workspace_commands",
    "workspace_index_status",
    "workspace_timeline_events",
    "workspace_conversations",
    "workspace_answer_notes",
    "workspace_conversation_messages",
    "workspace_model_experiments",
    "workspace_model_selections",
    "local_model_download_jobs",
    "workspace_skill_profiles",
    "workspace_saved_reports",
    "workspace_agent_workflows",
    "workspace_mcp_configs",
    "workspace_indexing_rules",
    "workspace_storage_stats",
]

_CATEGORY_KEYS = ("index", "conversations", "notes", "scan", "other")


class SQLiteWorkspaceStorageGateway:
    """Computes, caches and deletes per-workspace storage using the app's SQLite files.

    Knows both the main workspace database and the optional SQLite vector store
    (where embeddings live). Vector chunks are usually the heaviest part of a
    workspace, so they are counted into the ``index`` category when the vector
    store is SQLite-backed.
    """

    def __init__(
        self,
        workspace_db_path: str | Path,
        vector_store_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(str(workspace_db_path)).expanduser()
        self.vector_store_path = (
            Path(str(vector_store_path)).expanduser() if vector_store_path else None
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_workspace_schema(self.db_path)

    # ------------------------------------------------------------------ reads

    def get_or_compute(self, workspace_id: str) -> WorkspaceStorageBreakdown:
        cached = self.get_cached(workspace_id)
        if cached is not None:
            return cached
        return self.recompute(workspace_id)

    def get_cached(self, workspace_id: str) -> WorkspaceStorageBreakdown | None:
        with self._connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT total_bytes, breakdown_json, computed_at
                FROM workspace_storage_stats
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            categories = json.loads(row["breakdown_json"])
        except (json.JSONDecodeError, TypeError):
            categories = {}
        if not isinstance(categories, dict):
            categories = {}
        return WorkspaceStorageBreakdown(
            workspace_id=workspace_id,
            total_bytes=int(row["total_bytes"]),
            categories={str(key): int(value) for key, value in categories.items()},
            computed_at=row["computed_at"],
        )

    # -------------------------------------------------------------- mutations

    def recompute(self, workspace_id: str) -> WorkspaceStorageBreakdown:
        categories = dict.fromkeys(_CATEGORY_KEYS, 0)

        with self._connect(self.db_path) as connection:
            for category, sources in _MAIN_DB_SOURCES.items():
                for table, wid_column, columns in sources:
                    categories[category] += self._sum_columns(
                        connection, table, wid_column, columns, workspace_id
                    )

        categories["index"] += self._vector_store_bytes(workspace_id)

        total_bytes = sum(categories.values())
        computed_at = datetime.now(UTC).isoformat()
        self._save_cache(workspace_id, total_bytes, categories, computed_at)
        return WorkspaceStorageBreakdown(
            workspace_id=workspace_id,
            total_bytes=total_bytes,
            categories=categories,
            computed_at=computed_at,
        )

    def invalidate(self, workspace_id: str) -> None:
        with self._connect(self.db_path) as connection:
            connection.execute(
                "DELETE FROM workspace_storage_stats WHERE workspace_id = ?",
                (workspace_id,),
            )
            connection.commit()

    def delete_workspace_data(self, workspace_id: str) -> None:
        with self._connect(self.db_path) as connection:
            # Ratings are keyed by experiment_id; remove them via their experiments.
            connection.execute(
                """
                DELETE FROM workspace_model_experiment_ratings
                WHERE experiment_id IN (
                    SELECT id FROM workspace_model_experiments WHERE workspace_id = ?
                )
                """,
                (workspace_id,),
            )
            for table in _MAIN_DB_DELETE_TABLES:
                self._safe_execute(
                    connection,
                    f"DELETE FROM {table} WHERE workspace_id = ?",
                    (workspace_id,),
                )
            connection.commit()

    # ---------------------------------------------------------------- helpers

    def _save_cache(
        self,
        workspace_id: str,
        total_bytes: int,
        categories: dict[str, int],
        computed_at: str,
    ) -> None:
        with self._connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO workspace_storage_stats (
                    workspace_id, total_bytes, breakdown_json, computed_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    total_bytes = excluded.total_bytes,
                    breakdown_json = excluded.breakdown_json,
                    computed_at = excluded.computed_at
                """,
                (
                    workspace_id,
                    int(total_bytes),
                    json.dumps(categories, sort_keys=True),
                    computed_at,
                ),
            )
            connection.commit()

    def _vector_store_bytes(self, workspace_id: str) -> int:
        if self.vector_store_path is None or not self.vector_store_path.exists():
            return 0
        try:
            with self._connect(self.vector_store_path) as connection:
                return self._sum_columns(
                    connection,
                    "workspace_vector_chunks",
                    "workspace_id",
                    ["content", "embedding_json", "metadata_json"],
                    workspace_id,
                )
        except sqlite3.Error:
            return 0

    @staticmethod
    def _sum_columns(
        connection: sqlite3.Connection,
        table: str,
        wid_column: str,
        columns: list[str],
        workspace_id: str,
    ) -> int:
        expression = " + ".join(f"length(coalesce({column}, ''))" for column in columns)
        try:
            row = connection.execute(
                f"SELECT COALESCE(SUM({expression}), 0) FROM {table} WHERE {wid_column} = ?",
                (workspace_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            # Table or column absent on an older database file.
            return 0
        return int(row[0]) if row and row[0] is not None else 0

    @staticmethod
    def _safe_execute(
        connection: sqlite3.Connection,
        statement: str,
        parameters: tuple[object, ...],
    ) -> None:
        try:
            connection.execute(statement, parameters)
        except sqlite3.OperationalError:
            pass

    @staticmethod
    def _connect(db_path: Path) -> sqlite3.Connection:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = open_sqlite(db_path)
        connection.row_factory = sqlite3.Row
        return connection
