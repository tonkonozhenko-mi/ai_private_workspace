from app.core.domain.model_experiment_run import ModelExperimentRun
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort


class ModelExperimentRunNotFoundError(ValueError):
    pass


class GetModelExperimentRunUseCase:
    def __init__(self, repository: ModelExperimentRepositoryPort) -> None:
        self.repository = repository

    def execute(self, run_id: str) -> ModelExperimentRun:
        run = self.repository.get(run_id)
        if run is None:
            raise ModelExperimentRunNotFoundError("Model experiment not found")
        return run
