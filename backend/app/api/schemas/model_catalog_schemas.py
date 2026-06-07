from pydantic import BaseModel, Field

from app.core.domain.model_catalog import (
    LocalModelDefinition,
    ModelRecommendation,
    ModelRecommendationResult,
)


class LocalModelDefinitionResponse(BaseModel):
    id: str
    provider: str
    model_name: str
    model_type: str
    display_name: str
    description: str
    capabilities: list[str]
    recommended_for_profiles: list[str]
    recommended_laptop_profiles: list[str]
    estimated_size: str | None
    context_window: int | None
    embedding_dimension: int | None
    quality_tier: str
    speed_tier: str
    local_only: bool
    notes: list[str]


class RecommendModelsRequest(BaseModel):
    assistant_profile_id: str = Field(..., min_length=1)
    laptop_profile_id: str = Field(..., min_length=1)
    task_type: str = Field(..., min_length=1)
    model_type: str = Field(..., min_length=1)


class ModelRecommendationResponse(BaseModel):
    model: LocalModelDefinitionResponse
    score: int
    reasons: list[str]
    warnings: list[str]


class ModelRecommendationResultResponse(BaseModel):
    assistant_profile_id: str
    laptop_profile_id: str
    task_type: str
    model_type: str
    recommendations: list[ModelRecommendationResponse]


def to_local_model_definition_response(
    model: LocalModelDefinition,
) -> LocalModelDefinitionResponse:
    return LocalModelDefinitionResponse(
        id=model.id,
        provider=model.provider,
        model_name=model.model_name,
        model_type=model.model_type,
        display_name=model.display_name,
        description=model.description,
        capabilities=model.capabilities,
        recommended_for_profiles=model.recommended_for_profiles,
        recommended_laptop_profiles=model.recommended_laptop_profiles,
        estimated_size=model.estimated_size,
        context_window=model.context_window,
        embedding_dimension=model.embedding_dimension,
        quality_tier=model.quality_tier,
        speed_tier=model.speed_tier,
        local_only=model.local_only,
        notes=model.notes,
    )


def to_model_recommendation_response(
    recommendation: ModelRecommendation,
) -> ModelRecommendationResponse:
    return ModelRecommendationResponse(
        model=to_local_model_definition_response(recommendation.model),
        score=recommendation.score,
        reasons=recommendation.reasons,
        warnings=recommendation.warnings,
    )


def to_model_recommendation_result_response(
    result: ModelRecommendationResult,
) -> ModelRecommendationResultResponse:
    return ModelRecommendationResultResponse(
        assistant_profile_id=result.assistant_profile_id,
        laptop_profile_id=result.laptop_profile_id,
        task_type=result.task_type,
        model_type=result.model_type,
        recommendations=[
            to_model_recommendation_response(recommendation)
            for recommendation in result.recommendations
        ],
    )
