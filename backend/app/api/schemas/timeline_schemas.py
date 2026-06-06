from pydantic import BaseModel

from app.core.domain.timeline import TimelineEvent


class TimelineEventResponse(BaseModel):
    id: str
    workspace_id: str
    event_type: str
    title: str
    summary: str
    metadata: dict[str, str]
    created_at: str


def to_timeline_event_response(event: TimelineEvent) -> TimelineEventResponse:
    return TimelineEventResponse(
        id=event.id,
        workspace_id=event.workspace_id,
        event_type=event.event_type,
        title=event.title,
        summary=event.summary,
        metadata=event.metadata,
        created_at=event.created_at,
    )
