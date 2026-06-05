from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.domain.command_risk import classify_command_risk
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.command_errors import CommandWorkspaceNotFoundError


@dataclass(frozen=True)
class ProposeCommandInput:
    workspace_id: str
    command: str
    cwd: str
    reason: str


class ProposeCommandUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        command_repository: CommandRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.command_repository = command_repository

    def execute(self, request: ProposeCommandInput) -> CommandProposal:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise CommandWorkspaceNotFoundError("Workspace not found")

        proposal = CommandProposal(
            id=str(uuid4()),
            workspace_id=request.workspace_id,
            command=request.command,
            cwd=request.cwd,
            reason=request.reason,
            risk=classify_command_risk(request.command),
            status=CommandStatus.PENDING.value,
            created_at=datetime.now(UTC).isoformat(),
            approved_at=None,
            rejected_at=None,
            executed_at=None,
            stdout=None,
            stderr=None,
            exit_code=None,
        )
        return self.command_repository.create(proposal)
