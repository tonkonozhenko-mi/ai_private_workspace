from app.core.domain.workspace import Workspace
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


class ListWorkspacesUseCase:
    def __init__(self, workspace_repository: WorkspaceRepositoryPort) -> None:
        self.workspace_repository = workspace_repository

    def execute(self) -> list[Workspace]:
        return self.workspace_repository.list()
