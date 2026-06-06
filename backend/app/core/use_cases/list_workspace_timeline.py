from dataclasses import dataclass

from app.core.domain.timeline import TimelineEvent
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class ListWorkspaceTimelineInput:
    workspace_id: str
    limit: int = 50


class WorkspaceTimelineNotFoundError(ValueError):
    pass


class ListWorkspaceTimelineUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        timeline_repository: TimelineRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: ListWorkspaceTimelineInput) -> list[TimelineEvent]:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise WorkspaceTimelineNotFoundError("Workspace not found")

        return self.timeline_repository.list_by_workspace(
            workspace_id=request.workspace_id,
            limit=max(0, request.limit),
        )
