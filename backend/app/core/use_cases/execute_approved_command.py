from dataclasses import dataclass, replace
from datetime import UTC, datetime

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.command_runner import CommandRunnerPort
from app.core.use_cases.command_errors import CommandInvalidStatusError, CommandNotFoundError


@dataclass(frozen=True)
class ExecuteApprovedCommandInput:
    command_id: str


class ExecuteApprovedCommandUseCase:
    def __init__(
        self,
        command_repository: CommandRepositoryPort,
        command_runner: CommandRunnerPort,
    ) -> None:
        self.command_repository = command_repository
        self.command_runner = command_runner

    def execute(self, request: ExecuteApprovedCommandInput) -> CommandProposal:
        proposal = self.command_repository.get(request.command_id)
        if proposal is None:
            raise CommandNotFoundError("Command not found")
        if proposal.status != CommandStatus.APPROVED.value:
            raise CommandInvalidStatusError("Only approved commands can be executed")
        if proposal.policy_allowed is not True or proposal.policy_mode != "auto_executable":
            raise CommandInvalidStatusError(
                proposal.policy_reason
                or "Command is not allowed for automatic execution by policy"
            )

        result = self.command_runner.run(command=proposal.command, cwd=proposal.cwd)
        executed_proposal = replace(
            proposal,
            status=(
                CommandStatus.EXECUTED.value
                if result.exit_code == 0
                else CommandStatus.FAILED.value
            ),
            executed_at=datetime.now(UTC).isoformat(),
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )
        return self.command_repository.update(executed_proposal)
