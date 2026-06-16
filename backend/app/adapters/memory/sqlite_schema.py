import sqlite3
from pathlib import Path


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
                archived_at TEXT NULL,
                persistence TEXT NOT NULL DEFAULT 'saved'
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
            CREATE TABLE IF NOT EXISTS workspace_conversations (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pinned_at TEXT NULL,
                archived_at TEXT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_answer_notes (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source_question TEXT NULL,
                source_paths_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pinned_at TEXT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_conversation_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                sources_count INTEGER NOT NULL,
                used_context_chunks INTEGER NOT NULL,
                llm_provider TEXT NULL,
                llm_model TEXT NULL,
                prompt_tokens INTEGER NULL,
                completion_tokens INTEGER NULL,
                total_tokens INTEGER NULL,
                latency_ms INTEGER NULL,
                skill_profile_json TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]' 
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
            CREATE TABLE IF NOT EXISTS local_model_download_jobs (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                job_json TEXT NOT NULL,
                created_at TEXT NOT NULL
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
            CREATE TABLE IF NOT EXISTS workspace_saved_reports (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                report_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                export_markdown TEXT NOT NULL,
                export_text TEXT NOT NULL,
                report_json TEXT NOT NULL,
                generated_from_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                pinned_at TEXT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_agent_workflows (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                title TEXT NOT NULL,
                goal TEXT NOT NULL,
                provider TEXT NULL,
                model TEXT NULL,
                readiness TEXT NOT NULL,
                agent_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                guardrails_json TEXT NOT NULL,
                unsupported_actions_json TEXT NOT NULL,
                safety_note TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_mcp_configs (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                template_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                transport TEXT NOT NULL,
                command TEXT NOT NULL,
                args_json TEXT NOT NULL,
                env_json TEXT NOT NULL,
                config_json TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                scope TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                reviewed INTEGER NOT NULL,
                available_tools_json TEXT NOT NULL,
                approved_tools_json TEXT NOT NULL,
                denied_tools_json TEXT NOT NULL,
                guardrails_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_storage_stats (
                workspace_id TEXT PRIMARY KEY,
                total_bytes INTEGER NOT NULL,
                breakdown_json TEXT NOT NULL,
                computed_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_project_understanding (
                workspace_id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                index_signature TEXT NOT NULL,
                summary TEXT NOT NULL,
                risks_json TEXT NOT NULL DEFAULT '[]',
                sources_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_project_understanding",
            column_name="guide_json",
            column_definition="guide_json TEXT NOT NULL DEFAULT '{}'",
        )
        _add_column_if_missing(
            connection,
            table_name="workspaces",
            column_name="archived_at",
            column_definition="archived_at TEXT NULL",
        )
        _add_column_if_missing(
            connection,
            table_name="workspaces",
            column_name="persistence",
            column_definition="persistence TEXT NOT NULL DEFAULT 'saved'",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_conversations",
            column_name="pinned_at",
            column_definition="pinned_at TEXT NULL",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_conversations",
            column_name="archived_at",
            column_definition="archived_at TEXT NULL",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_conversation_messages",
            column_name="sources_json",
            column_definition="sources_json TEXT NOT NULL DEFAULT '[]'",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_answer_notes",
            column_name="source_paths_json",
            column_definition="source_paths_json TEXT NOT NULL DEFAULT '[]'",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_answer_notes",
            column_name="pinned_at",
            column_definition="pinned_at TEXT NULL",
        )
        _add_column_if_missing(
            connection,
            table_name="workspace_saved_reports",
            column_name="pinned_at",
            column_definition="pinned_at TEXT NULL",
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
