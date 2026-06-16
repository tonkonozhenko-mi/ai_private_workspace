from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.domain.command_risk import classify_command_risk
from app.core.domain.local_model_install_draft import (
    LocalModelInstallDraft,
    build_local_model_install_draft,
)
from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import (
    ModelCatalogRegistry,
    build_custom_ollama_model_definition,
)
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


class LocalModelInstallDraftWorkspaceNotFoundError(Exception):
    pass


class LocalModelInstallDraftValidationError(Exception):
    pass


@dataclass(frozen=True)
class CreateLocalModelInstallDraftInput:
    workspace_id: str
    provider: str
    model: str
    model_type: str | None = None


class CreateLocalModelInstallDraftUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        command_repository: CommandRepositoryPort,
        model_catalog_registry: ModelCatalogRegistry,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.command_repository = command_repository
        self.model_catalog_registry = model_catalog_registry
        self.timeline_repository = timeline_repository

    def execute(
        self,
        request: CreateLocalModelInstallDraftInput,
    ) -> LocalModelInstallDraft:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise LocalModelInstallDraftWorkspaceNotFoundError("Workspace not found")

        model = self._find_model(
            provider=request.provider,
            model=request.model,
            model_type=request.model_type,
        )
        command = f"ollama pull {model.model_name}"
        risk = classify_command_risk(command)
        proposal = CommandProposal(
            id=str(uuid4()),
            workspace_id=request.workspace_id,
            command=command,
            cwd=workspace.project_path,
            reason=(
                f"Draft local model download for {model.display_name}. "
                "This records user intent only and is not executable from the frontend."
            ),
            risk=risk,
            status=CommandStatus.PENDING.value,
            created_at=datetime.now(UTC).isoformat(),
            approved_at=None,
            rejected_at=None,
            executed_at=None,
            stdout=None,
            stderr=None,
            exit_code=None,
            policy_allowed=False,
            policy_mode="manual_only",
            policy_reason=(
                "Model downloads are intentionally manual-only until a controlled backend "
                "download worker is implemented."
            ),
        )
        created = self.command_repository.create(proposal)
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="model_install_draft_created",
                    title="Model download draft created",
                    summary=f"Prepared manual download draft for {model.display_name}.",
                    metadata={
                        "command_id": created.id,
                        "provider": model.provider,
                        "model": model.model_name,
                        "model_type": model.model_type,
                    },
                )
            )
        return build_local_model_install_draft(
            workspace_id=request.workspace_id,
            model=model,
            command_proposal=created,
        )

    def _find_model(
        self,
        *,
        provider: str,
        model: str,
        model_type: str | None,
    ) -> LocalModelDefinition:
        for candidate in self.model_catalog_registry.list_models():
            if candidate.provider != provider or candidate.model_name != model:
                continue
            if model_type is not None and candidate.model_type != model_type:
                continue
            if candidate.provider != "ollama":
                raise LocalModelInstallDraftValidationError(
                    "Only Ollama model download drafts are supported for now"
                )
            return candidate
        if provider == "ollama" and model_type in {"llm", "embedding"}:
            try:
                return self.model_catalog_registry.register_user_model(
                    build_custom_ollama_model_definition(model, model_type)
                )
            except (OSError, ValueError) as exc:
                raise LocalModelInstallDraftValidationError(str(exc)) from exc
        raise LocalModelInstallDraftValidationError("Model is not present in the local catalog")
