from dataclasses import dataclass

from app.core.domain.workspace import Workspace
from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.ports.workspace_storage_gateway import WorkspaceStorageGatewayPort


@dataclass(frozen=True)
class DeleteWorkspaceInput:
    workspace_id: str


class DeleteWorkspaceNotFoundError(ValueError):
    pass


class DeleteWorkspaceUseCase:
    """Permanently delete a workspace and all of its app-owned data.

    The project's files on disk are never touched - only the app's internal
    index, conversation history, scan, notes and metadata stored in SQLite.
    """

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        storage_gateway: WorkspaceStorageGatewayPort,
        vector_store: VectorStorePort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.storage_gateway = storage_gateway
        self.vector_store = vector_store

    def execute(self, request: DeleteWorkspaceInput) -> Workspace:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise DeleteWorkspaceNotFoundError("Workspace not found")

        if self.vector_store is not None:
            try:
                self.vector_store.clear_workspace(workspace_id=request.workspace_id)
            except Exception:  # noqa: BLE001 - deletion must not be blocked by vector store
                pass

        self.storage_gateway.delete_workspace_data(request.workspace_id)
        self.workspace_repository.delete(request.workspace_id)
        return workspace
