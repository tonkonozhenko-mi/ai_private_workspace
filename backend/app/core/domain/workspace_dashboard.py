from dataclasses import dataclass

from app.core.domain.assistant_profile import WorkspaceAssistantRecommendation
from app.core.domain.runtime_health import RuntimeHealth
from app.core.domain.timeline import TimelineEvent
from app.core.domain.workspace_quick_start import WorkspaceQuickStart
from app.core.domain.workspace_readiness import WorkspaceReadiness
from app.core.domain.workspace_summary import WorkspaceSummary


@dataclass(frozen=True)
class WorkspaceDashboard:
    workspace_id: str
    workspace_name: str
    assistant_mode: str
    status: str
    summary: WorkspaceSummary
    readiness: WorkspaceReadiness
    quick_start: WorkspaceQuickStart
    assistant_recommendation: WorkspaceAssistantRecommendation
    recent_events: list[TimelineEvent]
    runtime_health: RuntimeHealth
    primary_next_action_id: str | None
    primary_next_action_title: str | None
