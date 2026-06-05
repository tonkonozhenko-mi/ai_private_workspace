from app.core.domain.index_status import WorkspaceIndexStatus


class InMemoryIndexStatusRepository:
    def __init__(self) -> None:
        self._statuses: dict[str, WorkspaceIndexStatus] = {}

    def save(self, status: WorkspaceIndexStatus) -> WorkspaceIndexStatus:
        self._statuses[status.workspace_id] = status
        return status

    def get(self, workspace_id: str) -> WorkspaceIndexStatus | None:
        return self._statuses.get(workspace_id)
