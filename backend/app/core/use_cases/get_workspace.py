from app.core.domain.workspace import Workspace
from app.core.ports.workspace_repository import WorkspaceRepository


class GetWorkspaceUseCase:
    def __init__(self, workspace_repository: WorkspaceRepository) -> None:
        self.workspace_repository = workspace_repository

    def execute(self, workspace_id: str) -> Workspace | None:
        return self.workspace_repository.get_by_id(workspace_id)
