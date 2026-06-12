from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: datetime
    archived_at: str | None = None
