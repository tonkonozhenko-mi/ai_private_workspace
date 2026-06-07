from pydantic import BaseModel

from app.core.domain.assistant_profile import (
    AssistantProfile,
    WorkspaceAssistantRecommendation,
)


class AssistantProfileResponse(BaseModel):
    id: str
    name: str
    description: str
    target_users: list[str]
    primary_capabilities: list[str]
    recommended_actions: list[str]
    recommended_runtime: dict[str, str]


class WorkspaceAssistantRecommendationResponse(BaseModel):
    workspace_id: str
    assistant_mode: str
    profile: AssistantProfileResponse
    matched_skills: list[str]
    recommended_actions: list[str]
    missing_capabilities: list[str]


def to_assistant_profile_response(
    profile: AssistantProfile,
) -> AssistantProfileResponse:
    return AssistantProfileResponse(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        target_users=profile.target_users,
        primary_capabilities=profile.primary_capabilities,
        recommended_actions=profile.recommended_actions,
        recommended_runtime=profile.recommended_runtime,
    )


def to_workspace_assistant_recommendation_response(
    recommendation: WorkspaceAssistantRecommendation,
) -> WorkspaceAssistantRecommendationResponse:
    return WorkspaceAssistantRecommendationResponse(
        workspace_id=recommendation.workspace_id,
        assistant_mode=recommendation.assistant_mode,
        profile=to_assistant_profile_response(recommendation.profile),
        matched_skills=recommendation.matched_skills,
        recommended_actions=recommendation.recommended_actions,
        missing_capabilities=recommendation.missing_capabilities,
    )
