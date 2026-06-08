from pydantic import BaseModel, Field

from app.api.schemas.model_catalog_schemas import (
    LocalModelDefinitionResponse,
    to_local_model_definition_response,
)
from app.core.domain.workspace_model_recommendation import (
    WorkspaceModelRecommendation,
    WorkspaceModelRecommendationResult,
)


class RecommendWorkspaceModelsRequest(BaseModel):
    assistant_profile_id: str | None = Field(default=None, min_length=1)
    laptop_profile_id: str = Field(..., min_length=1)
    task_type: str = Field(..., min_length=1)
    model_type: str = Field(..., min_length=1)


class WorkspaceModelRecommendationResponse(BaseModel):
    model: LocalModelDefinitionResponse
    catalog_score: int
    performance_score: int | None
    final_score: int
    reasons: list[str]
    warnings: list[str]
    historical_signals: dict[str, str]


class WorkspaceModelRecommendationResultResponse(BaseModel):
    workspace_id: str
    assistant_profile_id: str
    laptop_profile_id: str
    task_type: str
    model_type: str
    recommendations: list[WorkspaceModelRecommendationResponse]
    notes: list[str]


def to_workspace_model_recommendation_response(
    recommendation: WorkspaceModelRecommendation,
) -> WorkspaceModelRecommendationResponse:
    return WorkspaceModelRecommendationResponse(
        model=to_local_model_definition_response(recommendation.model),
        catalog_score=recommendation.catalog_score,
        performance_score=recommendation.performance_score,
        final_score=recommendation.final_score,
        reasons=recommendation.reasons,
        warnings=recommendation.warnings,
        historical_signals=recommendation.historical_signals,
    )


def to_workspace_model_recommendation_result_response(
    result: WorkspaceModelRecommendationResult,
) -> WorkspaceModelRecommendationResultResponse:
    return WorkspaceModelRecommendationResultResponse(
        workspace_id=result.workspace_id,
        assistant_profile_id=result.assistant_profile_id,
        laptop_profile_id=result.laptop_profile_id,
        task_type=result.task_type,
        model_type=result.model_type,
        recommendations=[
            to_workspace_model_recommendation_response(recommendation)
            for recommendation in result.recommendations
        ],
        notes=result.notes,
    )
