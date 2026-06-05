from dataclasses import dataclass

from app.core.domain.skill import SkillMatch


@dataclass(frozen=True)
class SuggestedAction:
    id: str
    title: str
    description: str
    category: str
    priority: str


@dataclass(frozen=True)
class WorkspaceSummary:
    workspace_id: str
    name: str
    project_path: str
    assistant_mode: str
    privacy_mode: str
    created_at: str
    has_scan: bool
    detected_skills_count: int
    detected_skills: list[SkillMatch]
    suggested_actions: list[SuggestedAction]
