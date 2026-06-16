import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.workspace_model_selection import (
    WorkspaceModelSelection,
    WorkspaceSelectedModel,
)


class SQLiteWorkspaceModelSelectionRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def get(self, workspace_id: str) -> WorkspaceModelSelection | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT selection_json
                FROM workspace_model_selections
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        return self._from_dict(json.loads(row["selection_json"]))

    def save(self, selection: WorkspaceModelSelection) -> WorkspaceModelSelection:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_model_selections (
                    workspace_id,
                    selection_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    selection_json = excluded.selection_json,
                    updated_at = excluded.updated_at
                """,
                (
                    selection.workspace_id,
                    json.dumps(self._to_dict(selection), sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()
        return selection

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_dict(selection: WorkspaceModelSelection) -> dict:
        return {
            "workspace_id": selection.workspace_id,
            "selected_llm": SQLiteWorkspaceModelSelectionRepository._model_to_dict(
                selection.selected_llm
            ),
            "selected_embedding": (
                SQLiteWorkspaceModelSelectionRepository._model_to_dict(selection.selected_embedding)
            ),
            "notes": selection.notes,
        }

    @staticmethod
    def _model_to_dict(model: WorkspaceSelectedModel | None) -> dict | None:
        if model is None:
            return None
        return {
            "provider": model.provider,
            "model": model.model,
            "model_type": model.model_type,
            "selected_at": model.selected_at,
            "selected_reason": model.selected_reason,
        }

    @staticmethod
    def _from_dict(data: dict) -> WorkspaceModelSelection:
        return WorkspaceModelSelection(
            workspace_id=data["workspace_id"],
            selected_llm=SQLiteWorkspaceModelSelectionRepository._model_from_dict(
                data["selected_llm"]
            ),
            selected_embedding=(
                SQLiteWorkspaceModelSelectionRepository._model_from_dict(data["selected_embedding"])
            ),
            notes=list(data["notes"]),
        )

    @staticmethod
    def _model_from_dict(data: dict | None) -> WorkspaceSelectedModel | None:
        if data is None:
            return None
        return WorkspaceSelectedModel(
            provider=data["provider"],
            model=data["model"],
            model_type=data["model_type"],
            selected_at=data["selected_at"],
            selected_reason=data["selected_reason"],
        )
