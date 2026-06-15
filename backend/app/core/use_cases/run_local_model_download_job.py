from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4
import shlex
import threading

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
from app.core.ports.workspace_model_selection_repository import (
    WorkspaceModelSelectionRepositoryPort,
)
from app.core.use_cases.add_timeline_event import AddTimelineEventInput, AddTimelineEventUseCase
from app.core.use_cases.update_workspace_model_selection import (
    UpdateWorkspaceModelSelectionInput,
    UpdateWorkspaceModelSelectionUseCase,
)
from app.core.use_cases.command_errors import (
    CommandInvalidStatusError,
    CommandNotFoundError,
    CommandWorkspaceNotFoundError,
)
from app.core.use_cases.run_local_model_download import LocalModelDownloadExecutionDisabledError
from app.core.domain.command import CommandStatus


class LocalModelDownloadJobNotFoundError(Exception):
    pass


class LocalModelDownloadJobNotCancellableError(Exception):
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
        selection_repository: WorkspaceModelSelectionRepositoryPort | None = None,
        configuration: dict[str, str] | None = None,
    ) -> None:
        self.command_repository = command_repository
        self.command_runner = command_runner
        self.workspace_repository = workspace_repository
        self.model_catalog_registry = model_catalog_registry
        self.job_repository = job_repository
        self.timeline_repository = timeline_repository
        self.selection_repository = selection_repository
        self.configuration = dict(configuration or {})

    def start(
        self,
        *,
        command_id: str,
        execution_enabled: bool,
        command_runner_name: str,
    ) -> LocalModelDownloadJob:
        """Create a backend-owned job and return immediately.

        The previous foundation executed the pull inside the request/response cycle.
        From Task 209 onward, the request only records the approved intent and starts
        a background worker thread. The frontend polls GET /local-download-jobs/{id}.
        """
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

        approved = replace(
            proposal,
            status=CommandStatus.APPROVED.value,
            approved_at=proposal.approved_at or datetime.now(UTC).isoformat(),
            policy_allowed=True,
            policy_mode="model_download_background_job",
            policy_reason=(
                "Allowed only by the dedicated backend model download background worker after catalog validation."
            ),
        )
        self.command_repository.update(approved)
        self.job_repository.update(
            replace(
                job,
                command_proposal=approved,
                progress_message=(
                    "Download job queued. The backend worker will run it in the background; "
                    "the UI should poll job status."
                ),
            )
        )

        worker = threading.Thread(
            target=self._run_background_job,
            args=(job.id, approved.id, workspace.project_path, model),
            name=f"model-download-{job.id[:8]}",
            daemon=True,
        )
        worker.start()
        # Return the queued snapshot immediately. The job repository may already have
        # moved to running/succeeded by the time the client polls.
        return self.job_repository.get(job.id) or job

    def get(self, job_id: str) -> LocalModelDownloadJob:
        job = self.job_repository.get(job_id)
        if job is None:
            raise LocalModelDownloadJobNotFoundError("Model download job not found")
        return job

    def list(self, workspace_id: str | None = None) -> list[LocalModelDownloadJob]:
        return self.job_repository.list(workspace_id=workspace_id)

    def request_cancel(self, job_id: str) -> LocalModelDownloadJob:
        job = self.job_repository.get(job_id)
        if job is None:
            raise LocalModelDownloadJobNotFoundError("Model download job not found")

        if job.status in {"succeeded", "failed", "cancelled"}:
            raise LocalModelDownloadJobNotCancellableError("Finished model download jobs cannot be cancelled")

        now = datetime.now(UTC).isoformat()
        if job.status == "queued":
            cancelled_command = replace(
                job.command_proposal,
                status=CommandStatus.REJECTED.value,
                policy_allowed=False,
                policy_mode="model_download_cancelled_before_start",
                policy_reason="The user cancelled the queued model download before execution started.",
            )
            self.command_repository.update(cancelled_command)
            return self.job_repository.update(
                replace(
                    job,
                    status="cancelled",
                    progress_percent=100,
                    progress_message="Download cancelled before backend execution started.",
                    finished_at=now,
                    cancel_requested_at=now,
                    cancellable=False,
                    command_proposal=cancelled_command,
                    cancellation_summary="Cancelled safely while queued. No Ollama pull command was executed.",
                    next_steps=["Choose another model if needed.", "Create a new download draft when ready."],
                )
            )

        return self.job_repository.update(
            replace(
                job,
                cancel_requested_at=job.cancel_requested_at or now,
                cancellable=False,
                progress_message=(
                    "Cancel requested. The backend will not kill the Ollama process blindly; "
                    "the current pull will finish or fail and then record the final status."
                ),
                cancellation_summary=(
                    "Cancel was requested after the download had started. For safety this runtime records the request "
                    "but does not force-kill the model pull process."
                ),
                next_steps=[
                    "Wait for the safe final status.",
                    "Re-check installed models after the job finishes.",
                ],
            )
        )

    def _run_background_job(
        self,
        job_id: str,
        command_id: str,
        workspace_path: str,
        model: LocalModelDefinition,
    ) -> None:
        job = self.job_repository.get(job_id)
        proposal = self.command_repository.get(command_id)
        if job is None or proposal is None:
            return

        if job.status == "cancelled":
            return

        running_job = self.job_repository.update(
            replace(
                job,
                status="running",
                progress_percent=25,
                progress_message=f"Downloading {model.display_name} with backend-controlled Ollama worker…",
                started_at=datetime.now(UTC).isoformat(),
                cancellable=True,
                command_proposal=proposal,
            )
        )

        try:
            result = self.command_runner.run(
                command=proposal.command,
                cwd=workspace_path,
                allowed_root=workspace_path,
            )
            executed = replace(
                proposal,
                status=CommandStatus.EXECUTED.value if result.exit_code == 0 else CommandStatus.FAILED.value,
                executed_at=datetime.now(UTC).isoformat(),
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
            )
            updated_command = self.command_repository.update(executed)
            finished_status = "succeeded" if updated_command.status == CommandStatus.EXECUTED.value else "failed"
            progress_message = (
                f"{model.display_name} download finished. Re-check installed models."
                if finished_status == "succeeded"
                else f"{model.display_name} download failed. Review backend output."
            )
        except Exception as exc:  # noqa: BLE001 - background jobs must persist failures instead of crashing silently.
            updated_command = self.command_repository.update(
                replace(
                    proposal,
                    status=CommandStatus.FAILED.value,
                    executed_at=datetime.now(UTC).isoformat(),
                    stdout=proposal.stdout,
                    stderr=f"Background model download worker failed: {exc}",
                    exit_code=1,
                )
            )
            finished_status = "failed"
            progress_message = f"{model.display_name} download failed before completion. Review backend output."

        latest_job = self.job_repository.get(job_id) or running_job
        cancellation_tail = (
            " Cancel was requested during execution; the worker waited for the safe final result."
            if latest_job.cancel_requested_at
            else ""
        )
        finished_job = self.job_repository.update(
            replace(
                latest_job,
                status=finished_status,
                progress_percent=100,
                progress_message=progress_message + cancellation_tail,
                finished_at=datetime.now(UTC).isoformat(),
                cancellable=False,
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

        if finished_status == "succeeded":
            self._auto_select_downloaded_model(finished_job.workspace_id, model)

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

    def _auto_select_downloaded_model(
        self,
        workspace_id: str,
        model: LocalModelDefinition,
    ) -> None:
        """Make a freshly downloaded model the workspace's active choice.

        Only fills an empty slot so an explicit earlier choice is never silently
        overridden. Best-effort: a selection failure must not fail the download.
        """
        if self.selection_repository is None or model.model_type not in {"llm", "embedding"}:
            return
        try:
            current = self.selection_repository.get(workspace_id)
        except Exception:  # noqa: BLE001
            current = None
        if current is not None:
            already_chosen = (
                current.selected_llm
                if model.model_type == "llm"
                else current.selected_embedding
            )
            if already_chosen is not None:
                return
        try:
            UpdateWorkspaceModelSelectionUseCase(
                workspace_repository=self.workspace_repository,
                selection_repository=self.selection_repository,
                model_catalog_registry=self.model_catalog_registry,
                timeline_repository=self.timeline_repository,
                configuration=self.configuration,
            ).execute(
                UpdateWorkspaceModelSelectionInput(
                    workspace_id=workspace_id,
                    provider=model.provider,
                    model=model.model_name,
                    model_type=model.model_type,
                    selected_reason="Auto-selected after a successful local download.",
                )
            )
        except Exception:  # noqa: BLE001 - auto-select is a convenience, never block the job
            pass

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
