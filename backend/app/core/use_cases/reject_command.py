from dataclasses import dataclass, replace
from datetime import UTC, datetime

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.use_cases.command_errors import CommandInvalidStatusError, CommandNotFoundError


@dataclass(frozen=True)
class RejectCommandInput:
    command_id: str


class RejectCommandUseCase:
    def __init__(self, command_repository: CommandRepositoryPort) -> None:
        self.command_repository = command_repository

    def execute(self, request: RejectCommandInput) -> CommandProposal:
        proposal = self.command_repository.get(request.command_id)
        if proposal is None:
            raise CommandNotFoundError("Command not found")
        if proposal.status != CommandStatus.PENDING.value:
            raise CommandInvalidStatusError("Only pending commands can be rejected")

        rejected_proposal = replace(
            proposal,
            status=CommandStatus.REJECTED.value,
            rejected_at=datetime.now(UTC).isoformat(),
        )
        return self.command_repository.update(rejected_proposal)
