from app.core.domain.timeline import TimelineEvent


class InMemoryTimelineRepository:
    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    def add(self, event: TimelineEvent) -> TimelineEvent:
        self._events.append(event)
        return event

    def list_by_workspace(
        self,
        workspace_id: str,
        limit: int = 50,
    ) -> list[TimelineEvent]:
        events = [event for event in reversed(self._events) if event.workspace_id == workspace_id]
        return events[: max(0, limit)]
