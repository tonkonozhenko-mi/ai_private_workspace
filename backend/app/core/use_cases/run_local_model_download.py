import shlex
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.domain.local_model_download_execution import LocalModelDownloadExecutionResult
from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.command_runner import CommandRunnerPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import AddTimelineEventInput, AddTimelineEventUseCase
from app.core.use_cases.command_errors import (
    CommandInvalidStatusError,
    CommandNotFoundError,
    CommandWorkspaceNotFoundError,
)


class LocalModelDownloadExecutionDisabledError(Exception):
    pass


@dataclass(frozen=True)
class RunLocalModelDownloadInput:
    command_id: str
    execution_enabled: bool
    command_runner_name: str


class RunLocalModelDownloadUseCase:
    def __init__(
        self,
        command_repository: CommandRepositoryPort,
        command_runner: CommandRunnerPort,
        workspace_repository: WorkspaceRepositoryPort,
        model_catalog_registry: ModelCatalogRegistry,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.command_repository = command_repository
        self.command_runner = command_runner
        self.workspace_repository = workspace_repository
        self.model_catalog_registry = model_catalog_registry
        self.timeline_repository = timeline_repository

    def execute(self, request: RunLocalModelDownloadInput) -> LocalModelDownloadExecutionResult:
        if not request.execution_enabled:
            raise LocalModelDownloadExecutionDisabledError(
                "Backend model download execution is disabled. Enable it only in a trusted local desktop runtime."
            )
        if request.command_runner_name != "local":
            raise LocalModelDownloadExecutionDisabledError(
                "Real model downloads require COMMAND_RUNNER=local."
            )

        proposal = self.command_repository.get(request.command_id)
        if proposal is None:
            raise CommandNotFoundError("Command not found")
        if proposal.status not in {CommandStatus.PENDING.value, CommandStatus.APPROVED.value}:
            raise CommandInvalidStatusError(
                "Only pending or approved model download drafts can be run"
            )

        workspace = self.workspace_repository.get(proposal.workspace_id)
        if workspace is None:
            raise CommandWorkspaceNotFoundError("Workspace not found")

        model = self._validate_exact_ollama_pull(proposal)
        approved = replace(
            proposal,
            status=CommandStatus.APPROVED.value,
            approved_at=proposal.approved_at or datetime.now(UTC).isoformat(),
            policy_allowed=True,
            policy_mode="model_download_worker",
            policy_reason=(
                "Allowed only by the dedicated backend model download worker after catalog validation."
            ),
        )
        self.command_repository.update(approved)

        result = self.command_runner.run(
            command=approved.command,
            cwd=workspace.project_path,
            allowed_root=workspace.project_path,
        )
        executed = replace(
            approved,
            status=CommandStatus.EXECUTED.value
            if result.exit_code == 0
            else CommandStatus.FAILED.value,
            executed_at=datetime.now(UTC).isoformat(),
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )
        updated = self.command_repository.update(executed)

        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=updated.workspace_id,
                    event_type="model_download_executed",
                    title="Model download finished",
                    summary=f"Backend download for {model.display_name} finished with status {updated.status}.",
                    metadata={
                        "command_id": updated.id,
                        "provider": model.provider,
                        "model": model.model_name,
                        "exit_code": str(updated.exit_code),
                    },
                )
            )

        return LocalModelDownloadExecutionResult(
            command_id=updated.id,
            workspace_id=updated.workspace_id,
            provider=model.provider,
            model=model.model_name,
            display_name=model.display_name,
            status="completed" if updated.status == CommandStatus.EXECUTED.value else "failed",
            execution_status=updated.status,
            safety_summary=(
                "Executed by the backend model download worker after validating the exact Ollama catalog model. "
                "No frontend shell command was executed and no indexing/rebuild side effect was triggered."
            ),
            command_proposal=updated,
            next_steps=[
                "Re-check installed models.",
                "Save the model as workspace preference if needed.",
                "Build or rebuild search context only when you explicitly choose to do it.",
            ],
        )

    def _validate_exact_ollama_pull(self, proposal: CommandProposal) -> LocalModelDefinition:
        try:
            parts = shlex.split(proposal.command)
        except ValueError as exc:
            raise CommandInvalidStatusError(f"Invalid model download command: {exc}") from exc

        if len(parts) != 3 or parts[0] != "ollama" or parts[1] != "pull":
            raise CommandInvalidStatusError(
                "Only exact 'ollama pull <catalog-model-name>' commands are allowed"
            )

        requested_model = parts[2]
        for model in self.model_catalog_registry.list_models():
            if model.provider == "ollama" and model.model_name == requested_model:
                return model
        raise CommandInvalidStatusError(
            "Model download command does not match the local catalog allowlist"
        )
