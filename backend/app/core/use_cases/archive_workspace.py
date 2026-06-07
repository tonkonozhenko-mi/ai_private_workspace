from dataclasses import dataclass, replace
from datetime import UTC, datetime

from app.core.domain.workspace import Workspace
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


@dataclass(frozen=True)
class ArchiveWorkspaceInput:
    workspace_id: str


class ArchiveWorkspaceNotFoundError(ValueError):
    pass


class ArchiveWorkspaceUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: ArchiveWorkspaceInput) -> Workspace:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise ArchiveWorkspaceNotFoundError("Workspace not found")
        if workspace.archived_at is not None:
            return workspace

        archived_workspace = self.workspace_repository.update(
            replace(workspace, archived_at=datetime.now(UTC).isoformat())
        )
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=workspace.id,
                    event_type="workspace_archived",
                    title="Workspace archived",
                    summary=f"Archived workspace {workspace.name}.",
                    metadata={},
                )
            )
        return archived_workspace
