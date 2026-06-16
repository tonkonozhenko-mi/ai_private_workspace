from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating


class InMemoryModelExperimentRatingRepository:
    def __init__(self) -> None:
        self._ratings: list[ModelExperimentCandidateRating] = []

    def save(
        self,
        rating: ModelExperimentCandidateRating,
    ) -> ModelExperimentCandidateRating:
        self._ratings.append(rating)
        return rating

    def list_by_experiment(
        self,
        experiment_id: str,
    ) -> list[ModelExperimentCandidateRating]:
        return [rating for rating in self._ratings if rating.experiment_id == experiment_id]
