"""Record answer ratings and derive nudges from the recent history."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.domain.answer_rating import (
    AnswerRating,
    RatingNudge,
    RatingVerdict,
    compute_rating_nudges,
)
from app.core.ports.answer_rating_repository import AnswerRatingRepositoryPort


class AnswerRatingValidationError(ValueError):
    pass


@dataclass(frozen=True)
class RecordAnswerRatingInput:
    workspace_id: str
    verdict: str
    llm_model: str = ""
    context_chunks: int = 0


class RecordAnswerRatingUseCase:
    def __init__(self, repository: AnswerRatingRepositoryPort) -> None:
        self.repository = repository

    def execute(self, request: RecordAnswerRatingInput) -> AnswerRating:
        verdict = request.verdict.strip().lower()
        if verdict not in (RatingVerdict.UP, RatingVerdict.DOWN):
            raise AnswerRatingValidationError("verdict must be 'up' or 'down'")
        rating = AnswerRating(
            id=uuid.uuid4().hex,
            workspace_id=request.workspace_id,
            verdict=verdict,
            llm_model=(request.llm_model or "").strip(),
            context_chunks=max(0, int(request.context_chunks)),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return self.repository.add(rating)


class GetRatingNudgesUseCase:
    def __init__(self, repository: AnswerRatingRepositoryPort) -> None:
        self.repository = repository

    def execute(self, workspace_id: str) -> list[RatingNudge]:
        ratings = self.repository.list(workspace_id, limit=50)
        return compute_rating_nudges(ratings)
