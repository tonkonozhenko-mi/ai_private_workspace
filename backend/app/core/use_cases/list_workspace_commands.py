from dataclasses import dataclass

from app.core.domain.command import CommandProposal
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.command_errors import CommandWorkspaceNotFoundError


@dataclass(frozen=True)
class ListWorkspaceCommandsInput:
    workspace_id: str


class ListWorkspaceCommandsUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        command_repository: CommandRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.command_repository = command_repository

    def execute(self, request: ListWorkspaceCommandsInput) -> list[CommandProposal]:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise CommandWorkspaceNotFoundError("Workspace not found")

        return self.command_repository.list_by_workspace(request.workspace_id)
