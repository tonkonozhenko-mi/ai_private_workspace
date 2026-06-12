from dataclasses import dataclass

from app.core.domain.timeline import TimelineEvent


@dataclass(frozen=True)
class TimelineBackfillResult:
    workspace_id: str
    backfilled_events_count: int
    skipped_existing_events_count: int
    events: list[TimelineEvent]
