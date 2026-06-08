from typing import Protocol

from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating


class ModelExperimentRatingRepositoryPort(Protocol):
    def save(
        self,
        rating: ModelExperimentCandidateRating,
    ) -> ModelExperimentCandidateRating:
        """Persist a user rating for an experiment candidate."""

    def list_by_experiment(
        self,
        experiment_id: str,
    ) -> list[ModelExperimentCandidateRating]:
        """Return ratings for an experiment in creation order."""
