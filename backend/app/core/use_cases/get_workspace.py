from app.core.domain.workspace import Workspace
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


class GetWorkspaceUseCase:
    def __init__(self, workspace_repository: WorkspaceRepositoryPort) -> None:
        self.workspace_repository = workspace_repository

    def execute(self, workspace_id: str) -> Workspace | None:
        return self.workspace_repository.get(workspace_id)
