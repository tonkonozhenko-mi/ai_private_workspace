from pathlib import Path
import sqlite3


def initialize_workspace_schema(db_path: str | Path) -> None:
    database_path = Path(db_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                project_path TEXT NOT NULL,
                assistant_mode TEXT NOT NULL,
                privacy_mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                archived_at TEXT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_project_scans (
                workspace_id TEXT PRIMARY KEY,
                scan_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_commands (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                command TEXT NOT NULL,
                cwd TEXT NOT NULL,
                reason TEXT NOT NULL,
                risk TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                approved_at TEXT NULL,
                rejected_at TEXT NULL,
                executed_at TEXT NULL,
                stdout TEXT NULL,
                stderr TEXT NULL,
                exit_code INTEGER NULL,
                policy_allowed INTEGER NULL,
                policy_mode TEXT NULL,
                policy_reason TEXT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_index_status (
                workspace_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                indexed_files_count INTEGER NOT NULL,
                chunks_count INTEGER NOT NULL,
                skipped_files_count INTEGER NOT NULL,
                last_indexed_at TEXT NULL,
                last_error TEXT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_timeline_events (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_model_experiments (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                run_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_model_experiment_ratings (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                rating INTEGER NOT NULL,
                is_preferred INTEGER NOT NULL,
                tags_json TEXT NOT NULL,
                comment TEXT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_model_selections (
                workspace_id TEXT PRIMARY KEY,
                selection_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_skill_profiles (
                workspace_id TEXT PRIMARY KEY,
                profile TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_indexing_rules (
                workspace_id TEXT PRIMARY KEY,
                profile TEXT NOT NULL,
                include_patterns_json TEXT NOT NULL,
                exclude_patterns_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _add_column_if_missing(
            connection,
            table_name="workspaces",
            column_name="archived_at",
            column_definition="archived_at TEXT NULL",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_commands",
            column_name="policy_allowed",
            column_definition="policy_allowed INTEGER NULL",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_commands",
            column_name="policy_mode",
            column_definition="policy_mode TEXT NULL",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_commands",
            column_name="policy_reason",
            column_definition="policy_reason TEXT NULL",
        )
        connection.commit()


def _add_column_if_missing(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    existing_columns = {
        row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in existing_columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")
