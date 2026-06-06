from pydantic import BaseModel

from app.core.domain.timeline import TimelineEvent
from app.core.domain.timeline_backfill import TimelineBackfillResult


class TimelineEventResponse(BaseModel):
    id: str
    workspace_id: str
    event_type: str
    title: str
    summary: str
    metadata: dict[str, str]
    created_at: str


class TimelineBackfillResponse(BaseModel):
    workspace_id: str
    backfilled_events_count: int
    skipped_existing_events_count: int
    events: list[TimelineEventResponse]


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


def to_timeline_backfill_response(
    result: TimelineBackfillResult,
) -> TimelineBackfillResponse:
    return TimelineBackfillResponse(
        workspace_id=result.workspace_id,
        backfilled_events_count=result.backfilled_events_count,
        skipped_existing_events_count=result.skipped_existing_events_count,
        events=[to_timeline_event_response(event) for event in result.events],
    )
