from dataclasses import dataclass

from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.domain.workspace_storage import WorkspaceStorageBreakdown
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.ports.workspace_storage_gateway import WorkspaceStorageGatewayPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


@dataclass(frozen=True)
class ClearWorkspaceIndexInput:
    workspace_id: str


class ClearWorkspaceIndexNotFoundError(ValueError):
    pass


class ClearWorkspaceIndexUseCase:
    """Drop a workspace's search index (embeddings) to reclaim space.

    The workspace itself, its conversations and notes are kept. The project can
    be re-indexed at any time.
    """

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        vector_store: VectorStorePort,
        index_status_repository: IndexStatusRepositoryPort,
        storage_gateway: WorkspaceStorageGatewayPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.vector_store = vector_store
        self.index_status_repository = index_status_repository
        self.storage_gateway = storage_gateway
        self.timeline_repository = timeline_repository

    def execute(self, request: ClearWorkspaceIndexInput) -> WorkspaceStorageBreakdown:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise ClearWorkspaceIndexNotFoundError("Workspace not found")

        self.vector_store.clear_workspace(workspace_id=request.workspace_id)
        self.index_status_repository.save(
            WorkspaceIndexStatus(
                workspace_id=request.workspace_id,
                status="not_indexed",
                indexed_files_count=0,
                chunks_count=0,
                skipped_files_count=0,
                last_indexed_at=None,
                last_error=None,
            )
        )

        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=request.workspace_id,
                    event_type="workspace_index_cleared",
                    title="Search index cleared",
                    summary=f"Cleared the search index for {workspace.name}.",
                    metadata={},
                )
            )

        return self.storage_gateway.recompute(request.workspace_id)
