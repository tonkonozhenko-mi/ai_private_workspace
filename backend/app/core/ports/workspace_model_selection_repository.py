from typing import Protocol

from app.core.domain.workspace_model_selection import WorkspaceModelSelection


class WorkspaceModelSelectionRepositoryPort(Protocol):
    def get(self, workspace_id: str) -> WorkspaceModelSelection | None:
        """Return saved model selection metadata for a workspace."""

    def save(self, selection: WorkspaceModelSelection) -> WorkspaceModelSelection:
        """Persist workspace model selection metadata."""
