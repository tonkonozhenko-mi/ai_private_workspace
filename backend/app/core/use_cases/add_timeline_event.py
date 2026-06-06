from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.timeline import TimelineEvent
from app.core.ports.timeline_repository import TimelineRepositoryPort


@dataclass(frozen=True)
class AddTimelineEventInput:
    workspace_id: str
    event_type: str
    title: str
    summary: str
    metadata: dict[str, str]


class AddTimelineEventUseCase:
    def __init__(self, timeline_repository: TimelineRepositoryPort) -> None:
        self.timeline_repository = timeline_repository

    def execute(self, request: AddTimelineEventInput) -> TimelineEvent:
        event = TimelineEvent(
            id=str(uuid4()),
            workspace_id=request.workspace_id,
            event_type=request.event_type,
            title=request.title,
            summary=request.summary,
            metadata=request.metadata,
            created_at=datetime.now(UTC).isoformat(),
        )
        return self.timeline_repository.add(event)
