from datetime import UTC, datetime

import pytest

from app.adapters.commands.local_command_runner import LocalCommandRunner
from app.adapters.memory.in_memory_command_repository import InMemoryCommandRepository
from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.core.domain.workspace import Workspace
from app.core.use_cases.approve_command import ApproveCommandInput, ApproveCommandUseCase
from app.core.use_cases.command_errors import CommandInvalidStatusError
from app.core.use_cases.execute_approved_command import (
    ExecuteApprovedCommandInput,
    ExecuteApprovedCommandUseCase,
)
from app.core.use_cases.propose_command import ProposeCommandInput, ProposeCommandUseCase


def test_local_runner_executes_approved_policy_allowed_command(tmp_path) -> None:
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")
    workspace_repository, command_repository, workspace = _setup_repositories(tmp_path)
    proposed_command = ProposeCommandUseCase(
        workspace_repository=workspace_repository,
        command_repository=command_repository,
    ).execute(
        ProposeCommandInput(
            workspace_id=workspace.id,
            command="grep hello hello.txt",
            cwd=str(tmp_path),
            reason="Search for expected text",
        )
    )
    approved_command = ApproveCommandUseCase(command_repository).execute(
        ApproveCommandInput(command_id=proposed_command.id)
    )

    executed_command = ExecuteApprovedCommandUseCase(
        command_repository=command_repository,
        command_runner=LocalCommandRunner(),
        workspace_repository=workspace_repository,
    ).execute(ExecuteApprovedCommandInput(command_id=approved_command.id))

    assert executed_command.status == "executed"
    assert executed_command.stdout == "hello\n"
    assert executed_command.stderr == ""
    assert executed_command.exit_code == 0


def test_local_runner_does_not_execute_policy_blocked_command(tmp_path) -> None:
    workspace_repository, command_repository, workspace = _setup_repositories(tmp_path)
    proposed_command = ProposeCommandUseCase(
        workspace_repository=workspace_repository,
        command_repository=command_repository,
    ).execute(
        ProposeCommandInput(
            workspace_id=workspace.id,
            command="terraform apply",
            cwd=str(tmp_path),
            reason="Apply infrastructure",
        )
    )
    approved_command = ApproveCommandUseCase(command_repository).execute(
        ApproveCommandInput(command_id=proposed_command.id)
    )

    with pytest.raises(CommandInvalidStatusError) as exc_info:
        ExecuteApprovedCommandUseCase(
            command_repository=command_repository,
            command_runner=LocalCommandRunner(),
            workspace_repository=workspace_repository,
        ).execute(ExecuteApprovedCommandInput(command_id=approved_command.id))

    assert str(exc_info.value) == "Destructive commands are blocked by policy."
    assert command_repository.get(approved_command.id).status == "approved"


def test_local_runner_does_not_execute_manual_only_command(tmp_path) -> None:
    workspace_repository, command_repository, workspace = _setup_repositories(tmp_path)
    proposed_command = ProposeCommandUseCase(
        workspace_repository=workspace_repository,
        command_repository=command_repository,
    ).execute(
        ProposeCommandInput(
            workspace_id=workspace.id,
            command="python scripts/check.py",
            cwd=str(tmp_path),
            reason="Run custom script",
        )
    )
    approved_command = ApproveCommandUseCase(command_repository).execute(
        ApproveCommandInput(command_id=proposed_command.id)
    )

    with pytest.raises(CommandInvalidStatusError) as exc_info:
        ExecuteApprovedCommandUseCase(
            command_repository=command_repository,
            command_runner=LocalCommandRunner(),
            workspace_repository=workspace_repository,
        ).execute(ExecuteApprovedCommandInput(command_id=approved_command.id))

    assert (
        str(exc_info.value)
        == "Unknown-risk commands require manual execution outside the assistant."
    )
    assert command_repository.get(approved_command.id).status == "approved"


def test_local_runner_rejects_cwd_outside_workspace(tmp_path) -> None:
    workspace_root = tmp_path / "workspace"
    outside_root = tmp_path / "outside"
    workspace_root.mkdir()
    outside_root.mkdir()
    workspace_repository, command_repository, workspace = _setup_repositories(workspace_root)
    proposed_command = ProposeCommandUseCase(
        workspace_repository=workspace_repository,
        command_repository=command_repository,
    ).execute(
        ProposeCommandInput(
            workspace_id=workspace.id,
            command="grep hello hello.txt",
            cwd=str(outside_root),
            reason="Search outside workspace",
        )
    )
    approved_command = ApproveCommandUseCase(command_repository).execute(
        ApproveCommandInput(command_id=proposed_command.id)
    )

    with pytest.raises(CommandInvalidStatusError) as exc_info:
        ExecuteApprovedCommandUseCase(
            command_repository=command_repository,
            command_runner=LocalCommandRunner(),
            workspace_repository=workspace_repository,
        ).execute(ExecuteApprovedCommandInput(command_id=approved_command.id))

    assert (
        str(exc_info.value) == "Command working directory must be inside the workspace project path"
    )
    assert command_repository.get(approved_command.id).status == "approved"


def _setup_repositories(project_path) -> tuple:
    workspace_repository = InMemoryWorkspaceRepository()
    command_repository = InMemoryCommandRepository()
    workspace = Workspace(
        id="workspace-1",
        name="Example Workspace",
        project_path=str(project_path),
        assistant_mode="local",
        privacy_mode="private",
        created_at=datetime.now(UTC),
    )
    workspace_repository.create(workspace)
    return workspace_repository, command_repository, workspace
