from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.workspace import Workspace
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class CreateWorkspaceInput:
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str


class CreateWorkspaceUseCase:
    def __init__(self, workspace_repository: WorkspaceRepositoryPort) -> None:
        self.workspace_repository = workspace_repository

    def execute(self, request: CreateWorkspaceInput) -> Workspace:
        workspace = Workspace(
            id=str(uuid4()),
            name=request.name,
            project_path=request.project_path,
            assistant_mode=request.assistant_mode,
            privacy_mode=request.privacy_mode,
            created_at=datetime.now(UTC),
        )
        return self.workspace_repository.create(workspace)
