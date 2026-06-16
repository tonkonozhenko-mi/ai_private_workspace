from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.workspace import Workspace
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


@dataclass(frozen=True)
class CreateWorkspaceInput:
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    persistence: str = "saved"


class CreateWorkspaceUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: CreateWorkspaceInput) -> Workspace:
        persistence = (
            request.persistence if request.persistence in {"saved", "temporary"} else "saved"
        )
        workspace = Workspace(
            id=str(uuid4()),
            name=request.name,
            project_path=request.project_path,
            assistant_mode=request.assistant_mode,
            privacy_mode=request.privacy_mode,
            created_at=datetime.now(UTC),
            persistence=persistence,
        )
        created_workspace = self.workspace_repository.create(workspace)
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=created_workspace.id,
                    event_type="workspace_created",
                    title="Workspace created",
                    summary=f"Created workspace {created_workspace.name}.",
                    metadata={"project_path": created_workspace.project_path},
                )
            )
        return created_workspace
