from pydantic import BaseModel

from app.api.schemas.index_status_schemas import (
    WorkspaceIndexStatusResponse,
    to_workspace_index_status_response,
)
from app.api.schemas.timeline_schemas import (
    TimelineEventResponse,
    to_timeline_event_response,
)
from app.core.domain.skill import SkillMatch
from app.core.domain.workspace_summary import (
    CommandActivitySummary,
    SuggestedAction,
    WorkspaceSummary,
)


class SkillMatchResponse(BaseModel):
    name: str
    category: str
    confidence: str
    evidence: list[str]


class SuggestedActionResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str
    priority: str


class CommandActivitySummaryResponse(BaseModel):
    total_commands: int
    pending_commands: int
    approved_commands: int
    rejected_commands: int
    executed_commands: int
    failed_commands: int
    last_command_id: str | None
    last_command_status: str | None
    last_command: str | None


class WorkspaceSummaryResponse(BaseModel):
    workspace_id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: str
    has_scan: bool
    detected_skills_count: int
    detected_skills: list[SkillMatchResponse]
    suggested_actions: list[SuggestedActionResponse]
    command_activity: CommandActivitySummaryResponse
    index_status: WorkspaceIndexStatusResponse
    recent_events: list[TimelineEventResponse]


def to_skill_match_response(skill: SkillMatch) -> SkillMatchResponse:
    return SkillMatchResponse(
        name=skill.name,
        category=skill.category,
        confidence=skill.confidence,
        evidence=skill.evidence,
    )


def to_suggested_action_response(action: SuggestedAction) -> SuggestedActionResponse:
    return SuggestedActionResponse(
        id=action.id,
        title=action.title,
        description=action.description,
        category=action.category,
        priority=action.priority,
    )


def to_command_activity_summary_response(
    activity: CommandActivitySummary,
) -> CommandActivitySummaryResponse:
    return CommandActivitySummaryResponse(
        total_commands=activity.total_commands,
        pending_commands=activity.pending_commands,
        approved_commands=activity.approved_commands,
        rejected_commands=activity.rejected_commands,
        executed_commands=activity.executed_commands,
        failed_commands=activity.failed_commands,
        last_command_id=activity.last_command_id,
        last_command_status=activity.last_command_status,
        last_command=activity.last_command,
    )


def to_workspace_summary_response(
    summary: WorkspaceSummary,
) -> WorkspaceSummaryResponse:
    return WorkspaceSummaryResponse(
        workspace_id=summary.workspace_id,
        name=summary.name,
        project_path=summary.project_path,
        assistant_mode=summary.assistant_mode,
        privacy_mode=summary.privacy_mode,
        created_at=summary.created_at,
        has_scan=summary.has_scan,
        detected_skills_count=summary.detected_skills_count,
        detected_skills=[to_skill_match_response(skill) for skill in summary.detected_skills],
        suggested_actions=[
            to_suggested_action_response(action) for action in summary.suggested_actions
        ],
        command_activity=to_command_activity_summary_response(summary.command_activity),
        index_status=to_workspace_index_status_response(summary.index_status),
        recent_events=[to_timeline_event_response(event) for event in summary.recent_events],
    )
