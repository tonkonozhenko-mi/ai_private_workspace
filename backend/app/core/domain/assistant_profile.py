from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantProfile:
    id: str
    name: str
    description: str
    target_users: list[str]
    primary_capabilities: list[str]
    recommended_actions: list[str]
    recommended_runtime: dict[str, str]


@dataclass(frozen=True)
class WorkspaceAssistantRecommendation:
    workspace_id: str
    assistant_mode: str
    profile: AssistantProfile
    matched_skills: list[str]
    recommended_actions: list[str]
    missing_capabilities: list[str]
