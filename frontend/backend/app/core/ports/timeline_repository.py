from typing import Protocol

from app.core.domain.timeline import TimelineEvent


class TimelineRepositoryPort(Protocol):
    def add(self, event: TimelineEvent) -> TimelineEvent:
        """Persist a workspace timeline event."""

    def list_by_workspace(
        self,
        workspace_id: str,
        limit: int = 50,
    ) -> list[TimelineEvent]:
        """Return the newest workspace timeline events first."""
