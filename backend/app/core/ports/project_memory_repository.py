from typing import Protocol

from app.core.domain.project_memory import MemoryItem


class ProjectMemoryRepositoryPort(Protocol):
    def add(self, item: MemoryItem) -> MemoryItem:
        """Persist a memory item."""

    def list(self, workspace_id: str) -> list[MemoryItem]:
        """All memory items for a workspace, newest first."""

    def delete(self, workspace_id: str, item_id: str) -> None:
        """Remove a memory item."""

    def delete_kind(self, workspace_id: str, kind: str) -> None:
        """Remove all items of a kind (used to replace the singleton handbook)."""

    def set_pinned(self, workspace_id: str, item_id: str, pinned: bool) -> None:
        """Pin or unpin an item."""

    def clear(self, workspace_id: str) -> None:
        """Remove all memory for a workspace."""
