from typing import Protocol

from app.core.domain.workspace import Workspace


class WorkspaceRepository(Protocol):
    def save(self, workspace: Workspace) -> Workspace:
        """Persist a workspace."""

    def get_by_id(self, workspace_id: str) -> Workspace | None:
        """Return a workspace by id, if it exists."""

    def list(self) -> list[Workspace]:
        """Return all workspaces."""
