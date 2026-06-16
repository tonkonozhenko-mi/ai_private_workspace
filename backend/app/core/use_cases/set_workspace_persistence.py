from dataclasses import dataclass, replace

from app.core.domain.workspace import Workspace
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)

VALID_PERSISTENCE = {"saved", "temporary"}


@dataclass(frozen=True)
class SetWorkspacePersistenceInput:
    workspace_id: str
    persistence: str


class SetWorkspacePersistenceNotFoundError(ValueError):
    pass


class SetWorkspacePersistenceValidationError(ValueError):
    pass


class SetWorkspacePersistenceUseCase:
    """Change whether a workspace is kept ('saved') or ephemeral ('temporary').

    Used by the "Keep forever" action to promote a temporary project to a
    permanent one.
    """

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: SetWorkspacePersistenceInput) -> Workspace:
        if request.persistence not in VALID_PERSISTENCE:
            raise SetWorkspacePersistenceValidationError(
                "persistence must be 'saved' or 'temporary'"
            )
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise SetWorkspacePersistenceNotFoundError("Workspace not found")
        if workspace.persistence == request.persistence:
            return workspace

        updated = self.workspace_repository.update(
            replace(workspace, persistence=request.persistence)
        )
        if self.timeline_repository is not None and request.persistence == "saved":
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=workspace.id,
                    event_type="workspace_kept",
                    title="Project kept",
                    summary=f"{workspace.name} is now a permanent project.",
                    metadata={},
                )
            )
        return updated
