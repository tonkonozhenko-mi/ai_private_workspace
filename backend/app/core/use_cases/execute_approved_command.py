from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.command_runner import CommandRunnerPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.command_errors import (
    CommandInvalidStatusError,
    CommandNotFoundError,
    CommandWorkspaceNotFoundError,
)


@dataclass(frozen=True)
class ExecuteApprovedCommandInput:
    command_id: str


class ExecuteApprovedCommandUseCase:
    def __init__(
        self,
        command_repository: CommandRepositoryPort,
        command_runner: CommandRunnerPort,
        workspace_repository: WorkspaceRepositoryPort,
    ) -> None:
        self.command_repository = command_repository
        self.command_runner = command_runner
        self.workspace_repository = workspace_repository

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

        workspace = self.workspace_repository.get(proposal.workspace_id)
        if workspace is None:
            raise CommandWorkspaceNotFoundError("Workspace not found")

        if not self._is_inside_workspace(
            cwd=proposal.cwd,
            workspace_root=workspace.project_path,
        ):
            raise CommandInvalidStatusError(
                "Command working directory must be inside the workspace project path"
            )

        result = self.command_runner.run(
            command=proposal.command,
            cwd=proposal.cwd,
            allowed_root=workspace.project_path,
        )
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

    @staticmethod
    def _is_inside_workspace(cwd: str, workspace_root: str) -> bool:
        cwd_path = Path(cwd).resolve()
        workspace_path = Path(workspace_root).resolve()

        try:
            cwd_path.relative_to(workspace_path)
        except ValueError:
            return False

        return True
