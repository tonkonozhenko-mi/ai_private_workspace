from dataclasses import dataclass

from app.core.domain.workspace_storage import WorkspaceStorageBreakdown
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.ports.workspace_storage_gateway import WorkspaceStorageGatewayPort


@dataclass(frozen=True)
class GetWorkspaceStorageInput:
    workspace_id: str
    recompute: bool = False


class GetWorkspaceStorageNotFoundError(ValueError):
    pass


class GetWorkspaceStorageUseCase:
    """Return the storage breakdown for a workspace (cached, or recomputed)."""

    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        storage_gateway: WorkspaceStorageGatewayPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.storage_gateway = storage_gateway

    def execute(self, request: GetWorkspaceStorageInput) -> WorkspaceStorageBreakdown:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise GetWorkspaceStorageNotFoundError("Workspace not found")
        if request.recompute:
            return self.storage_gateway.recompute(request.workspace_id)
        return self.storage_gateway.get_or_compute(request.workspace_id)
