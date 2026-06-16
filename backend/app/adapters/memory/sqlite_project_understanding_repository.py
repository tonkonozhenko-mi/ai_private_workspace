import json
from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.project_understanding import ProjectRisk, ProjectUnderstanding


class SQLiteProjectUnderstandingRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save(self, understanding: ProjectUnderstanding) -> ProjectUnderstanding:
        risks_json = json.dumps(
            [
                {"text": risk.text, "file": risk.source_file}
                for risk in understanding.risks
            ],
            sort_keys=True,
        )
        sources_json = json.dumps(list(understanding.sources), sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_project_understanding (
                    workspace_id,
                    model,
                    generated_at,
                    index_signature,
                    summary,
                    risks_json,
                    sources_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    model = excluded.model,
                    generated_at = excluded.generated_at,
                    index_signature = excluded.index_signature,
                    summary = excluded.summary,
                    risks_json = excluded.risks_json,
                    sources_json = excluded.sources_json
                """,
                (
                    understanding.workspace_id,
                    understanding.model,
                    understanding.generated_at,
                    understanding.index_signature,
                    understanding.summary,
                    risks_json,
                    sources_json,
                ),
            )
            connection.commit()
        return understanding

    def get(self, workspace_id: str) -> ProjectUnderstanding | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    workspace_id,
                    model,
                    generated_at,
                    index_signature,
                    summary,
                    risks_json,
                    sources_json
                FROM workspace_project_understanding
                WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()

        if row is None:
            return None
        risks = [
            ProjectRisk(text=entry.get("text", ""), source_file=entry.get("file"))
            for entry in json.loads(row["risks_json"])
        ]
        sources = list(json.loads(row["sources_json"]))
        return ProjectUnderstanding(
            workspace_id=row["workspace_id"],
            model=row["model"],
            generated_at=row["generated_at"],
            index_signature=row["index_signature"],
            summary=row["summary"],
            risks=risks,
            sources=sources,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
