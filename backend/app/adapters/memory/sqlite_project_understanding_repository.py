import json
import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.project_understanding import (
    ProjectRisk,
    ProjectRunCommand,
    ProjectStartPoint,
    ProjectUnderstanding,
)


class SQLiteProjectUnderstandingRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save(self, understanding: ProjectUnderstanding) -> ProjectUnderstanding:
        risks_json = json.dumps(
            [{"text": risk.text, "file": risk.source_file} for risk in understanding.risks],
            sort_keys=True,
        )
        sources_json = json.dumps(list(understanding.sources), sort_keys=True)
        guide_json = json.dumps(
            {
                "architecture": understanding.architecture,
                "start_here": [
                    {"file": point.file, "reason": point.reason}
                    for point in understanding.start_here
                ],
                "run_commands": [
                    {"command": command.command, "note": command.note}
                    for command in understanding.run_commands
                ],
            },
            sort_keys=True,
        )
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
                    sources_json,
                    guide_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    model = excluded.model,
                    generated_at = excluded.generated_at,
                    index_signature = excluded.index_signature,
                    summary = excluded.summary,
                    risks_json = excluded.risks_json,
                    sources_json = excluded.sources_json,
                    guide_json = excluded.guide_json
                """,
                (
                    understanding.workspace_id,
                    understanding.model,
                    understanding.generated_at,
                    understanding.index_signature,
                    understanding.summary,
                    risks_json,
                    sources_json,
                    guide_json,
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
                    sources_json,
                    guide_json
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
        guide = _load_guide(row["guide_json"] if "guide_json" in row.keys() else "{}")
        return ProjectUnderstanding(
            workspace_id=row["workspace_id"],
            model=row["model"],
            generated_at=row["generated_at"],
            index_signature=row["index_signature"],
            summary=row["summary"],
            risks=risks,
            sources=sources,
            architecture=guide["architecture"],
            start_here=guide["start_here"],
            run_commands=guide["run_commands"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


def _load_guide(guide_json: str | None) -> dict:
    empty = {"architecture": "", "start_here": [], "run_commands": []}
    if not guide_json:
        return empty
    try:
        payload = json.loads(guide_json)
    except (ValueError, TypeError):
        return empty
    if not isinstance(payload, dict):
        return empty
    architecture = payload.get("architecture")
    start_here = [
        ProjectStartPoint(file=entry.get("file", ""), reason=entry.get("reason", ""))
        for entry in payload.get("start_here", [])
        if isinstance(entry, dict) and entry.get("file")
    ]
    run_commands = [
        ProjectRunCommand(command=entry.get("command", ""), note=entry.get("note", ""))
        for entry in payload.get("run_commands", [])
        if isinstance(entry, dict) and entry.get("command")
    ]
    return {
        "architecture": architecture if isinstance(architecture, str) else "",
        "start_here": start_here,
        "run_commands": run_commands,
    }
