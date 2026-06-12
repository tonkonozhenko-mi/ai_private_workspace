from dataclasses import dataclass, replace

from app.core.domain.assistant_profile_registry import AssistantProfileRegistry
from app.core.domain.workspace import Workspace
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


SUPPORTED_PRIVACY_MODES = {"local_only", "private"}


@dataclass(frozen=True)
class UpdateWorkspaceMetadataInput:
    workspace_id: str
    name: str | None = None
    assistant_mode: str | None = None
    privacy_mode: str | None = None


class UpdateWorkspaceMetadataNotFoundError(ValueError):
    pass


class UpdateWorkspaceMetadataValidationError(ValueError):
    pass


class UpdateWorkspaceMetadataUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
        assistant_profile_registry: AssistantProfileRegistry | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.timeline_repository = timeline_repository
        self.assistant_profile_registry = (
            assistant_profile_registry or AssistantProfileRegistry()
        )

    def execute(self, request: UpdateWorkspaceMetadataInput) -> Workspace:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise UpdateWorkspaceMetadataNotFoundError("Workspace not found")

        values = {
            "name": workspace.name,
            "assistant_mode": workspace.assistant_mode,
            "privacy_mode": workspace.privacy_mode,
        }
        updated_fields: list[str] = []

        if request.name is not None:
            name = request.name.strip()
            if not name:
                raise UpdateWorkspaceMetadataValidationError(
                    "Workspace name cannot be empty"
                )
            self._set_changed(values, updated_fields, "name", name)

        if request.assistant_mode is not None:
            assistant_mode = request.assistant_mode.strip()
            profile_ids = {
                profile.id
                for profile in self.assistant_profile_registry.list_profiles()
            }
            if assistant_mode not in profile_ids:
                raise UpdateWorkspaceMetadataValidationError(
                    f"Unknown assistant profile: {assistant_mode}"
                )
            self._set_changed(
                values,
                updated_fields,
                "assistant_mode",
                assistant_mode,
            )

        if request.privacy_mode is not None:
            privacy_mode = request.privacy_mode.strip()
            if privacy_mode not in SUPPORTED_PRIVACY_MODES:
                raise UpdateWorkspaceMetadataValidationError(
                    f"Unsupported privacy mode: {privacy_mode}"
                )
            self._set_changed(
                values,
                updated_fields,
                "privacy_mode",
                privacy_mode,
            )

        if not updated_fields:
            return workspace

        updated_workspace = self.workspace_repository.update(
            replace(
                workspace,
                name=values["name"],
                assistant_mode=values["assistant_mode"],
                privacy_mode=values["privacy_mode"],
            )
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=workspace.id,
                    event_type="workspace_metadata_updated",
                    title="Workspace metadata updated",
                    summary=f"Updated metadata for workspace {updated_workspace.name}.",
                    metadata={"updated_fields": ",".join(updated_fields)},
                )
            )
        return updated_workspace

    @staticmethod
    def _set_changed(
        values: dict[str, str],
        updated_fields: list[str],
        field_name: str,
        value: str,
    ) -> None:
        if values[field_name] != value:
            values[field_name] = value
            updated_fields.append(field_name)
