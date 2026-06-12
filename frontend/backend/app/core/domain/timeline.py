from dataclasses import dataclass


@dataclass(frozen=True)
class TimelineEvent:
    id: str
    workspace_id: str
    event_type: str
    title: str
    summary: str
    metadata: dict[str, str]
    created_at: str
