from dataclasses import dataclass

from app.core.ports.vector_store import VectorStorePort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.ports.workspace_storage_gateway import WorkspaceStorageGatewayPort


@dataclass(frozen=True)
class PurgeTemporaryWorkspacesResult:
    deleted_count: int
    deleted_ids: list[str]


class PurgeTemporaryWorkspacesUseCase:
    """Delete every temporary workspace and all of its app-owned data.

    Called when the user confirms, on quit, that ephemeral projects should be
    forgotten. Project files on disk are never touched.
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

    def execute(self) -> PurgeTemporaryWorkspacesResult:
        temporary = [
            workspace
            for workspace in self.workspace_repository.list()
            if workspace.persistence == "temporary"
        ]
        deleted_ids: list[str] = []
        for workspace in temporary:
            if self.vector_store is not None:
                try:
                    self.vector_store.clear_workspace(workspace_id=workspace.id)
                except Exception:  # noqa: BLE001 - purge must not be blocked by vector store
                    pass
            self.storage_gateway.delete_workspace_data(workspace.id)
            self.workspace_repository.delete(workspace.id)
            deleted_ids.append(workspace.id)
        return PurgeTemporaryWorkspacesResult(
            deleted_count=len(deleted_ids),
            deleted_ids=deleted_ids,
        )
