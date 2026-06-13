from pydantic import BaseModel

from app.core.domain.guided_model_setup import (
    GuidedModelSetupGuide,
    GuidedModelSetupOption,
    GuidedModelSetupSection,
)


class GuidedModelSetupOptionResponse(BaseModel):
    provider: str
    model: str
    model_type: str
    display_name: str
    description: str
    recommendation_label: str
    recommended: bool
    local_only: bool
    quality_tier: str
    speed_tier: str
    estimated_size: str | None = None
    fit: str | None = None
    fit_label: str | None = None
    notes: list[str]


class GuidedModelSetupSectionResponse(BaseModel):
    model_type: str
    title: str
    purpose: str
    recommendation_summary: str
    custom_model_hint: str
    options: list[GuidedModelSetupOptionResponse]


class GuidedModelSetupGuideResponse(BaseModel):
    workspace_id: str
    title: str
    summary: str
    llm: GuidedModelSetupSectionResponse
    embedding: GuidedModelSetupSectionResponse
    packaging_notes: list[str]
    safety_notes: list[str]


def to_guided_model_setup_option_response(
    option: GuidedModelSetupOption,
) -> GuidedModelSetupOptionResponse:
    return GuidedModelSetupOptionResponse(**option.__dict__)


def to_guided_model_setup_section_response(
    section: GuidedModelSetupSection,
) -> GuidedModelSetupSectionResponse:
    return GuidedModelSetupSectionResponse(
        model_type=section.model_type,
        title=section.title,
        purpose=section.purpose,
        recommendation_summary=section.recommendation_summary,
        custom_model_hint=section.custom_model_hint,
        options=[to_guided_model_setup_option_response(option) for option in section.options],
    )


def to_guided_model_setup_guide_response(
    guide: GuidedModelSetupGuide,
) -> GuidedModelSetupGuideResponse:
    return GuidedModelSetupGuideResponse(
        workspace_id=guide.workspace_id,
        title=guide.title,
        summary=guide.summary,
        llm=to_guided_model_setup_section_response(guide.llm),
        embedding=to_guided_model_setup_section_response(guide.embedding),
        packaging_notes=guide.packaging_notes,
        safety_notes=guide.safety_notes,
    )
