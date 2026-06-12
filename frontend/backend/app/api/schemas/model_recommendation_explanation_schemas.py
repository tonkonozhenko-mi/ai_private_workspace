from pydantic import BaseModel, Field

from app.core.domain.model_recommendation_explanation import (
    ModelRecommendationExplanation,
    ModelRecommendationExplanationSection,
)


class ExplainWorkspaceModelRecommendationRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    model_type: str = Field(..., min_length=1)
    assistant_profile_id: str | None = Field(default=None, min_length=1)
    laptop_profile_id: str = Field(..., min_length=1)
    task_type: str = Field(..., min_length=1)


class ModelRecommendationExplanationSectionResponse(BaseModel):
    title: str
    bullets: list[str]


class ModelRecommendationExplanationResponse(BaseModel):
    workspace_id: str
    provider: str
    model: str
    model_type: str
    display_name: str | None
    summary: str
    sections: list[ModelRecommendationExplanationSectionResponse]
    recommended_actions: list[str]
    warnings: list[str]
    notes: list[str]


def to_model_recommendation_explanation_section_response(
    section: ModelRecommendationExplanationSection,
) -> ModelRecommendationExplanationSectionResponse:
    return ModelRecommendationExplanationSectionResponse(
        title=section.title,
        bullets=section.bullets,
    )


def to_model_recommendation_explanation_response(
    explanation: ModelRecommendationExplanation,
) -> ModelRecommendationExplanationResponse:
    return ModelRecommendationExplanationResponse(
        workspace_id=explanation.workspace_id,
        provider=explanation.provider,
        model=explanation.model,
        model_type=explanation.model_type,
        display_name=explanation.display_name,
        summary=explanation.summary,
        sections=[
            to_model_recommendation_explanation_section_response(section)
            for section in explanation.sections
        ],
        recommended_actions=explanation.recommended_actions,
        warnings=explanation.warnings,
        notes=explanation.notes,
    )
