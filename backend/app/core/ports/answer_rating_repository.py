from typing import Protocol

from app.core.domain.answer_rating import AnswerRating


class AnswerRatingRepositoryPort(Protocol):
    def add(self, rating: AnswerRating) -> AnswerRating:
        """Persist a rating."""

    def list(self, workspace_id: str, limit: int = 50) -> list[AnswerRating]:
        """Recent ratings for a workspace, newest first."""
