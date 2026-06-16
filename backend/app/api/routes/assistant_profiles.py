from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    index_status_repository,
    project_scan_repository,
    readiness_configuration,
    workspace_repository,
)
from app.api.schemas.assistant_profile_schemas import (
    AssistantProfileResponse,
    WorkspaceAssistantRecommendationResponse,
    to_assistant_profile_response,
    to_workspace_assistant_recommendation_response,
)
from app.core.use_cases.get_workspace_assistant_recommendation import (
    GetWorkspaceAssistantRecommendationInput,
    GetWorkspaceAssistantRecommendationUseCase,
    WorkspaceAssistantRecommendationNotFoundError,
)
from app.core.use_cases.list_assistant_profiles import ListAssistantProfilesUseCase

router = APIRouter(tags=["assistant-profiles"])


@router.get("/assistant-profiles", response_model=list[AssistantProfileResponse])
def list_assistant_profiles() -> list[AssistantProfileResponse]:
    profiles = ListAssistantProfilesUseCase().execute()
    return [to_assistant_profile_response(profile) for profile in profiles]


@router.get(
    "/workspaces/{workspace_id}/assistant-recommendation",
    response_model=WorkspaceAssistantRecommendationResponse,
)
def get_workspace_assistant_recommendation(
    workspace_id: str,
) -> WorkspaceAssistantRecommendationResponse:
    use_case = GetWorkspaceAssistantRecommendationUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
        index_status_repository=index_status_repository,
        configuration=readiness_configuration,
    )

    try:
        recommendation = use_case.execute(
            GetWorkspaceAssistantRecommendationInput(workspace_id=workspace_id)
        )
    except WorkspaceAssistantRecommendationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_workspace_assistant_recommendation_response(recommendation)
