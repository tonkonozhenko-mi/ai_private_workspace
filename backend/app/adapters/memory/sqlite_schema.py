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
                created_at TEXT NOT NULL
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
                exit_code INTEGER NULL
            )
            """
        )
        connection.commit()
