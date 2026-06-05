from pydantic import BaseModel

from app.core.domain.skill import SkillMatch
from app.core.domain.workspace_summary import SuggestedAction, WorkspaceSummary


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
        detected_skills=[
            to_skill_match_response(skill) for skill in summary.detected_skills
        ],
        suggested_actions=[
            to_suggested_action_response(action)
            for action in summary.suggested_actions
        ],
    )
