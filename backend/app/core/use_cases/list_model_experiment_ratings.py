from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating
from app.core.ports.model_experiment_rating_repository import (
    ModelExperimentRatingRepositoryPort,
)
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort


class ModelExperimentRatingsNotFoundError(ValueError):
    pass


class ListModelExperimentRatingsUseCase:
    def __init__(
        self,
        model_experiment_repository: ModelExperimentRepositoryPort,
        rating_repository: ModelExperimentRatingRepositoryPort,
    ) -> None:
        self.model_experiment_repository = model_experiment_repository
        self.rating_repository = rating_repository

    def execute(self, experiment_id: str) -> list[ModelExperimentCandidateRating]:
        if self.model_experiment_repository.get(experiment_id) is None:
            raise ModelExperimentRatingsNotFoundError("Model experiment not found")
        return self.rating_repository.list_by_experiment(experiment_id)
