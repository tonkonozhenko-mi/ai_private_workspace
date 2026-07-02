import json
import sqlite3
from pathlib import Path

from app.adapters.memory.sqlite_connection import open_sqlite
from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.model_experiment_run import (
    ModelExperimentCandidateResult,
    ModelExperimentRun,
)


class SQLiteModelExperimentRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save(self, run: ModelExperimentRun) -> ModelExperimentRun:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_model_experiments (
                    id,
                    workspace_id,
                    run_json,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_id = excluded.workspace_id,
                    run_json = excluded.run_json,
                    created_at = excluded.created_at
                """,
                (
                    run.id,
                    run.workspace_id,
                    json.dumps(self._to_dict(run), sort_keys=True),
                    run.created_at,
                ),
            )
            connection.commit()
        return run

    def get(self, run_id: str) -> ModelExperimentRun | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_json
                FROM workspace_model_experiments
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        return None if row is None else self._from_dict(json.loads(row["run_json"]))

    def list_by_workspace(
        self,
        workspace_id: str,
        limit: int = 20,
    ) -> list[ModelExperimentRun]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_json
                FROM workspace_model_experiments
                WHERE workspace_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (workspace_id, max(0, limit)),
            ).fetchall()
        return [self._from_dict(json.loads(row["run_json"])) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = open_sqlite(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_dict(run: ModelExperimentRun) -> dict:
        return {
            "id": run.id,
            "workspace_id": run.workspace_id,
            "question": run.question,
            "experiment_type": run.experiment_type,
            "status": run.status,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
            "shared_context_sources_count": run.shared_context_sources_count,
            "candidates": [
                {
                    "provider": candidate.provider,
                    "model": candidate.model,
                    "status": candidate.status,
                    "answer": candidate.answer,
                    "error": candidate.error,
                    "llm_provider": candidate.llm_provider,
                    "llm_model": candidate.llm_model,
                    "used_context_chunks": candidate.used_context_chunks,
                    "sources_count": candidate.sources_count,
                    "quality_warnings_count": candidate.quality_warnings_count,
                    "latency_ms": candidate.latency_ms,
                }
                for candidate in run.candidates
            ],
            "notes": run.notes,
        }

    @staticmethod
    def _from_dict(data: dict) -> ModelExperimentRun:
        return ModelExperimentRun(
            id=data["id"],
            workspace_id=data["workspace_id"],
            question=data["question"],
            experiment_type=data["experiment_type"],
            status=data["status"],
            created_at=data["created_at"],
            completed_at=data["completed_at"],
            shared_context_sources_count=data["shared_context_sources_count"],
            candidates=[
                ModelExperimentCandidateResult(
                    provider=candidate["provider"],
                    model=candidate["model"],
                    status=candidate["status"],
                    answer=candidate["answer"],
                    error=candidate["error"],
                    llm_provider=candidate["llm_provider"],
                    llm_model=candidate["llm_model"],
                    used_context_chunks=candidate["used_context_chunks"],
                    sources_count=candidate["sources_count"],
                    quality_warnings_count=candidate["quality_warnings_count"],
                    latency_ms=candidate["latency_ms"],
                )
                for candidate in data["candidates"]
            ],
            notes=list(data["notes"]),
        )
