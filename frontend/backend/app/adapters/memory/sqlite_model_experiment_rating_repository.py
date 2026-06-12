import json
from pathlib import Path
import sqlite3

from app.adapters.memory.sqlite_schema import initialize_workspace_schema
from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating


class SQLiteModelExperimentRatingRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        initialize_workspace_schema(self.db_path)

    def save(
        self,
        rating: ModelExperimentCandidateRating,
    ) -> ModelExperimentCandidateRating:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_model_experiment_ratings (
                    id,
                    experiment_id,
                    provider,
                    model,
                    rating,
                    is_preferred,
                    tags_json,
                    comment,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rating.id,
                    rating.experiment_id,
                    rating.provider,
                    rating.model,
                    rating.rating,
                    int(rating.is_preferred),
                    json.dumps(rating.tags),
                    rating.comment,
                    rating.created_at,
                ),
            )
            connection.commit()
        return rating

    def list_by_experiment(
        self,
        experiment_id: str,
    ) -> list[ModelExperimentCandidateRating]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    experiment_id,
                    provider,
                    model,
                    rating,
                    is_preferred,
                    tags_json,
                    comment,
                    created_at
                FROM workspace_model_experiment_ratings
                WHERE experiment_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (experiment_id,),
            ).fetchall()

        return [
            ModelExperimentCandidateRating(
                id=row["id"],
                experiment_id=row["experiment_id"],
                provider=row["provider"],
                model=row["model"],
                rating=row["rating"],
                is_preferred=bool(row["is_preferred"]),
                tags=list(json.loads(row["tags_json"])),
                comment=row["comment"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
