import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.command import CommandProposal
from app.core.domain.local_model_download_job import LocalModelDownloadJob


class SQLiteLocalModelDownloadJobRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def create(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        return self._save(job)

    def get(self, job_id: str) -> LocalModelDownloadJob | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT job_json FROM local_model_download_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return None if row is None else self._from_dict(json.loads(row["job_json"]))

    def update(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        return self._save(job)

    def list(self, workspace_id: str | None = None) -> list[LocalModelDownloadJob]:
        query = "SELECT job_json FROM local_model_download_jobs"
        params: tuple = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY created_at DESC, rowid DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._from_dict(json.loads(row["job_json"])) for row in rows]

    def _save(self, job: LocalModelDownloadJob) -> LocalModelDownloadJob:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO local_model_download_jobs (id, workspace_id, job_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workspace_id = excluded.workspace_id,
                    job_json = excluded.job_json,
                    created_at = excluded.created_at
                """,
                (
                    job.id,
                    job.workspace_id,
                    json.dumps(asdict(job), sort_keys=True),
                    job.created_at,
                ),
            )
            connection.commit()
        return job

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _from_dict(data: dict) -> LocalModelDownloadJob:
        return LocalModelDownloadJob(
            **{
                **data,
                "command_proposal": CommandProposal(**data["command_proposal"]),
                "next_steps": list(data["next_steps"]),
            }
        )
