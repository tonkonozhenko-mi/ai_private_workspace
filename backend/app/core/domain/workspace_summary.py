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
class CommandActivitySummary:
    total_commands: int
    pending_commands: int
    approved_commands: int
    rejected_commands: int
    executed_commands: int
    failed_commands: int
    last_command_id: str | None
    last_command_status: str | None
    last_command: str | None


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
    command_activity: CommandActivitySummary
