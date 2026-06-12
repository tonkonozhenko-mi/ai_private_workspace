from typing import Protocol


class MemoryStore(Protocol):
    def get(self, workspace_id: str, key: str) -> str | None:
        """Read a persisted memory value for a workspace."""

    def set(self, workspace_id: str, key: str, value: str) -> None:
        """Write a persisted memory value for a workspace."""
