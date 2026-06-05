from app.adapters.commands.fake_command_runner import FakeCommandRunner
from app.adapters.commands.local_command_runner import LocalCommandRunner
from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.adapters.memory.in_memory_command_repository import InMemoryCommandRepository
from app.adapters.memory.in_memory_project_scan_repository import (
    InMemoryProjectScanRepository,
)
from app.adapters.memory.in_memory_workspace_repository import InMemoryWorkspaceRepository
from app.adapters.memory.sqlite_command_repository import SQLiteCommandRepository
from app.adapters.memory.sqlite_project_scan_repository import SQLiteProjectScanRepository
from app.adapters.memory.sqlite_workspace_repository import SQLiteWorkspaceRepository
from app.config.settings import get_settings
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.command_runner import CommandRunnerPort
from app.core.ports.project_scan_repository import ProjectScanRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


def build_workspace_repository() -> WorkspaceRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryWorkspaceRepository()
    if repository_type == "sqlite":
        return SQLiteWorkspaceRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_project_scan_repository() -> ProjectScanRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryProjectScanRepository()
    if repository_type == "sqlite":
        return SQLiteProjectScanRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_command_repository() -> CommandRepositoryPort:
    settings = get_settings()
    repository_type = settings.workspace_repository.lower()

    if repository_type == "memory":
        return InMemoryCommandRepository()
    if repository_type == "sqlite":
        return SQLiteCommandRepository(settings.workspace_db_path)

    raise ValueError(f"Unsupported workspace repository: {settings.workspace_repository}")


def build_command_runner() -> CommandRunnerPort:
    settings = get_settings()
    runner_type = settings.command_runner.lower()

    if runner_type == "local":
        return LocalCommandRunner(
            timeout_seconds=settings.command_timeout_seconds,
            output_limit_chars=settings.command_output_limit_chars,
        )
    if runner_type == "fake":
        return FakeCommandRunner()

    raise ValueError(f"Unsupported command runner: {settings.command_runner}")


workspace_repository = build_workspace_repository()
project_scan_repository = build_project_scan_repository()
command_repository = build_command_repository()
file_system = LocalFileSystem()
command_runner = build_command_runner()
