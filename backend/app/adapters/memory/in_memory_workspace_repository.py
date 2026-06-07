from threading import Lock

from app.core.domain.workspace import Workspace


class InMemoryWorkspaceRepository:
    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}
        self._lock = Lock()

    def create(self, workspace: Workspace) -> Workspace:
        with self._lock:
            self._workspaces[workspace.id] = workspace
        return workspace

    def get(self, workspace_id: str) -> Workspace | None:
        with self._lock:
            return self._workspaces.get(workspace_id)

    def list(self) -> list[Workspace]:
        with self._lock:
            return list(self._workspaces.values())

    def update(self, workspace: Workspace) -> Workspace:
        with self._lock:
            self._workspaces[workspace.id] = workspace
        return workspace

    def save(self, workspace: Workspace) -> Workspace:
        return self.update(workspace)

    def get_by_id(self, workspace_id: str) -> Workspace | None:
        return self.get(workspace_id)
