from dataclasses import dataclass

from app.core.domain.model_experiment_run import ModelExperimentRun
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class ListWorkspaceModelExperimentsInput:
    workspace_id: str
    limit: int = 20


class WorkspaceModelExperimentsNotFoundError(ValueError):
    pass


class ListWorkspaceModelExperimentsUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        model_experiment_repository: ModelExperimentRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.model_experiment_repository = model_experiment_repository

    def execute(
        self,
        request: ListWorkspaceModelExperimentsInput,
    ) -> list[ModelExperimentRun]:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise WorkspaceModelExperimentsNotFoundError("Workspace not found")
        return self.model_experiment_repository.list_by_workspace(
            request.workspace_id,
            max(0, request.limit),
        )
