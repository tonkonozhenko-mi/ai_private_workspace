from typing import Protocol

from app.core.domain.model_experiment_run import ModelExperimentRun


class ModelExperimentRepositoryPort(Protocol):
    def save(self, run: ModelExperimentRun) -> ModelExperimentRun:
        """Persist a model experiment run."""

    def get(self, run_id: str) -> ModelExperimentRun | None:
        """Return a model experiment run by id, if it exists."""

    def list_by_workspace(
        self,
        workspace_id: str,
        limit: int = 20,
    ) -> list[ModelExperimentRun]:
        """Return newest model experiment runs for a workspace."""
