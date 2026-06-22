"""In-memory answer-rating store (tests and the memory backend)."""

from app.core.domain.answer_rating import AnswerRating


class InMemoryAnswerRatingRepository:
    def __init__(self) -> None:
        self._ratings: list[AnswerRating] = []

    def add(self, rating: AnswerRating) -> AnswerRating:
        self._ratings.append(rating)
        return rating

    def list(self, workspace_id: str, limit: int = 50) -> list[AnswerRating]:
        items = [r for r in self._ratings if r.workspace_id == workspace_id]
        items.sort(key=lambda r: r.created_at, reverse=True)
        return items[:limit]
