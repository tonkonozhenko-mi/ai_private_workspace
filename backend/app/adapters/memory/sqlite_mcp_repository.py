import json
import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.mcp_server import WorkspaceMCPServerConfig


class SQLiteMCPRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save_config(self, config: WorkspaceMCPServerConfig) -> WorkspaceMCPServerConfig:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workspace_mcp_configs (
                    id, workspace_id, template_id, name, category, transport, command,
                    args_json, env_json, config_json, risk_level, scope, enabled,
                    reviewed, available_tools_json, approved_tools_json, denied_tools_json,
                    guardrails_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    config.id,
                    config.workspace_id,
                    config.template_id,
                    config.name,
                    config.category,
                    config.transport,
                    config.command,
                    json.dumps(config.args, sort_keys=True),
                    json.dumps(config.env, sort_keys=True),
                    json.dumps(config.config_json, sort_keys=True),
                    config.risk_level,
                    config.scope,
                    1 if config.enabled else 0,
                    1 if config.reviewed else 0,
                    json.dumps(config.available_tools, sort_keys=True),
                    json.dumps(config.approved_tools, sort_keys=True),
                    json.dumps(config.denied_tools, sort_keys=True),
                    json.dumps(config.guardrails, sort_keys=True),
                    config.created_at,
                    config.updated_at,
                ),
            )
            connection.commit()
        return config

    def get_config(self, workspace_id: str, config_id: str) -> WorkspaceMCPServerConfig | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspace_mcp_configs WHERE workspace_id = ? AND id = ?",
                (workspace_id, config_id),
            ).fetchone()
        return self._from_row(row) if row else None

    def list_configs(self, workspace_id: str) -> list[WorkspaceMCPServerConfig]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM workspace_mcp_configs WHERE workspace_id = ? ORDER BY updated_at DESC, rowid DESC",
                (workspace_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def delete_config(self, workspace_id: str, config_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM workspace_mcp_configs WHERE workspace_id = ? AND id = ?",
                (workspace_id, config_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        connection = open_sqlite(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _from_row(self, row: sqlite3.Row) -> WorkspaceMCPServerConfig:
        return WorkspaceMCPServerConfig(
            id=row["id"],
            workspace_id=row["workspace_id"],
            template_id=row["template_id"],
            name=row["name"],
            category=row["category"],
            transport=row["transport"],
            command=row["command"],
            args=list(json.loads(row["args_json"] or "[]")),
            env=dict(json.loads(row["env_json"] or "{}")),
            config_json=dict(json.loads(row["config_json"] or "{}")),
            risk_level=row["risk_level"],
            scope=row["scope"],
            enabled=bool(row["enabled"]),
            reviewed=bool(row["reviewed"]),
            available_tools=list(json.loads(row["available_tools_json"] or "[]")),
            approved_tools=list(json.loads(row["approved_tools_json"] or "[]")),
            denied_tools=list(json.loads(row["denied_tools_json"] or "[]")),
            guardrails=list(json.loads(row["guardrails_json"] or "[]")),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
