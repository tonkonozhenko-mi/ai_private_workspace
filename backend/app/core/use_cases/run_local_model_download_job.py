from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4
import shlex

from app.core.domain.local_model_download_job import (
    LocalModelDownloadJob,
    build_queued_model_download_job,
)
from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.command_runner import CommandRunnerPort
from app.core.ports.local_model_download_job_repository import (
    LocalModelDownloadJobRepositoryPort,
)
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import AddTimelineEventInput, AddTimelineEventUseCase
from app.core.use_cases.command_errors import (
    CommandInvalidStatusError,
    CommandNotFoundError,
    CommandWorkspaceNotFoundError,
)
from app.core.use_cases.run_local_model_download import LocalModelDownloadExecutionDisabledError
from app.core.domain.command import CommandStatus


class LocalModelDownloadJobNotFoundError(Exception):
    pass


class RunLocalModelDownloadJobUseCase:
    def __init__(
        self,
        command_repository: CommandRepositoryPort,
        command_runner: CommandRunnerPort,
        workspace_repository: WorkspaceRepositoryPort,
        model_catalog_registry: ModelCatalogRegistry,
        job_repository: LocalModelDownloadJobRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.command_repository = command_repository
        self.command_runner = command_runner
        self.workspace_repository = workspace_repository
        self.model_catalog_registry = model_catalog_registry
        self.job_repository = job_repository
        self.timeline_repository = timeline_repository

    def start(
        self,
        *,
        command_id: str,
        execution_enabled: bool,
        command_runner_name: str,
    ) -> LocalModelDownloadJob:
        if not execution_enabled:
            raise LocalModelDownloadExecutionDisabledError(
                "Backend model download execution is disabled. Enable it only in a trusted local desktop runtime."
            )
        if command_runner_name != "local":
            raise LocalModelDownloadExecutionDisabledError(
                "Real model downloads require COMMAND_RUNNER=local."
            )

        proposal = self.command_repository.get(command_id)
        if proposal is None:
            raise CommandNotFoundError("Command not found")
        if proposal.status not in {CommandStatus.PENDING.value, CommandStatus.APPROVED.value}:
            raise CommandInvalidStatusError("Only pending or approved model download drafts can be run")

        workspace = self.workspace_repository.get(proposal.workspace_id)
        if workspace is None:
            raise CommandWorkspaceNotFoundError("Workspace not found")

        model = self._validate_exact_ollama_pull(proposal)
        now = datetime.now(UTC).isoformat()
        job = self.job_repository.create(
            build_queued_model_download_job(
                job_id=str(uuid4()),
                command_id=proposal.id,
                workspace_id=proposal.workspace_id,
                provider=model.provider,
                model=model.model_name,
                display_name=model.display_name,
                created_at=now,
                command_proposal=proposal,
            )
        )
        running = self.job_repository.update(
            replace(
                job,
                status="running",
                progress_percent=15,
                progress_message=f"Downloading {model.display_name} with backend-controlled Ollama worker…",
                started_at=datetime.now(UTC).isoformat(),
            )
        )

        approved = replace(
            proposal,
            status=CommandStatus.APPROVED.value,
            approved_at=proposal.approved_at or datetime.now(UTC).isoformat(),
            policy_allowed=True,
            policy_mode="model_download_worker_job",
            policy_reason=(
                "Allowed only by the dedicated backend model download job after catalog validation."
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
            status=CommandStatus.EXECUTED.value if result.exit_code == 0 else CommandStatus.FAILED.value,
            executed_at=datetime.now(UTC).isoformat(),
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
        )
        updated_command = self.command_repository.update(executed)
        finished_status = "succeeded" if updated_command.status == CommandStatus.EXECUTED.value else "failed"
        finished_job = self.job_repository.update(
            replace(
                running,
                status=finished_status,
                progress_percent=100,
                progress_message=(
                    f"{model.display_name} download finished. Re-check installed models."
                    if finished_status == "succeeded"
                    else f"{model.display_name} download failed. Review backend output."
                ),
                finished_at=datetime.now(UTC).isoformat(),
                command_proposal=updated_command,
                stdout_preview=_preview(updated_command.stdout),
                stderr_preview=_preview(updated_command.stderr),
                exit_code=updated_command.exit_code,
                next_steps=[
                    "Re-check installed models.",
                    "Save the model as workspace preference if needed.",
                    "Build or rebuild search context only when you explicitly choose to do it.",
                ],
            )
        )

        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=finished_job.workspace_id,
                    event_type="model_download_job_finished",
                    title="Model download job finished",
                    summary=f"Backend download job for {model.display_name} finished with status {finished_job.status}.",
                    metadata={
                        "job_id": finished_job.id,
                        "command_id": updated_command.id,
                        "provider": model.provider,
                        "model": model.model_name,
                        "exit_code": str(updated_command.exit_code),
                    },
                )
            )

        return finished_job

    def get(self, job_id: str) -> LocalModelDownloadJob:
        job = self.job_repository.get(job_id)
        if job is None:
            raise LocalModelDownloadJobNotFoundError("Model download job not found")
        return job

    def _validate_exact_ollama_pull(self, proposal) -> LocalModelDefinition:
        try:
            parts = shlex.split(proposal.command)
        except ValueError as exc:
            raise CommandInvalidStatusError(f"Invalid model download command: {exc}") from exc

        if len(parts) != 3 or parts[0] != "ollama" or parts[1] != "pull":
            raise CommandInvalidStatusError("Only exact 'ollama pull <catalog-model-name>' commands are allowed")

        requested_model = parts[2]
        for model in self.model_catalog_registry.list_models():
            if model.provider == "ollama" and model.model_name == requested_model:
                return model
        raise CommandInvalidStatusError("Model download command does not match the local catalog allowlist")


def _preview(value: str | None, limit: int = 4000) -> str | None:
    if value is None:
        return None
    return value[:limit]
