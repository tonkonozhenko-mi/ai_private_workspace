from dataclasses import dataclass

from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


@dataclass(frozen=True)
class GetWorkspaceIndexStatusInput:
    workspace_id: str


class WorkspaceIndexStatusNotFoundError(ValueError):
    pass


class GetWorkspaceIndexStatusUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.index_status_repository = index_status_repository

    def execute(
        self,
        request: GetWorkspaceIndexStatusInput,
    ) -> WorkspaceIndexStatus:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceIndexStatusNotFoundError("Workspace not found")

        saved_status = self.index_status_repository.get(request.workspace_id)
        if saved_status is not None:
            return saved_status

        return WorkspaceIndexStatus(
            workspace_id=request.workspace_id,
            status="not_indexed",
            indexed_files_count=0,
            chunks_count=0,
            skipped_files_count=0,
            last_indexed_at=None,
            last_error=None,
        )
