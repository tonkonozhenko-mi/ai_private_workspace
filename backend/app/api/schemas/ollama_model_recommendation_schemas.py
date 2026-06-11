from pydantic import BaseModel

from app.api.schemas.model_catalog_schemas import (
    LocalModelDefinitionResponse,
    to_local_model_definition_response,
)
from app.core.domain.ollama_model_recommendations import (
    OllamaHardwareProfile,
    OllamaModelRecommendationGuide,
    OllamaModelRole,
)


class OllamaModelRoleResponse(BaseModel):
    id: str
    title: str
    model_type: str
    default_model: str
    purpose: str
    why_it_matters: str


class OllamaHardwareProfileResponse(BaseModel):
    id: str
    title: str
    summary: str
    recommended_llm: str
    fallback_llm: str
    recommended_embedding: str
    notes: list[str]


class OllamaModelRecommendationGuideResponse(BaseModel):
    title: str
    summary: str
    default_profile_id: str
    roles: list[OllamaModelRoleResponse]
    profiles: list[OllamaHardwareProfileResponse]
    catalog_models: list[LocalModelDefinitionResponse]
    safety_notes: list[str]
    next_steps: list[str]


def to_ollama_model_role_response(role: OllamaModelRole) -> OllamaModelRoleResponse:
    return OllamaModelRoleResponse(
        id=role.id,
        title=role.title,
        model_type=role.model_type,
        default_model=role.default_model,
        purpose=role.purpose,
        why_it_matters=role.why_it_matters,
    )


def to_ollama_hardware_profile_response(
    profile: OllamaHardwareProfile,
) -> OllamaHardwareProfileResponse:
    return OllamaHardwareProfileResponse(
        id=profile.id,
        title=profile.title,
        summary=profile.summary,
        recommended_llm=profile.recommended_llm,
        fallback_llm=profile.fallback_llm,
        recommended_embedding=profile.recommended_embedding,
        notes=profile.notes,
    )


def to_ollama_model_recommendation_guide_response(
    guide: OllamaModelRecommendationGuide,
) -> OllamaModelRecommendationGuideResponse:
    return OllamaModelRecommendationGuideResponse(
        title=guide.title,
        summary=guide.summary,
        default_profile_id=guide.default_profile_id,
        roles=[to_ollama_model_role_response(role) for role in guide.roles],
        profiles=[to_ollama_hardware_profile_response(profile) for profile in guide.profiles],
        catalog_models=[
            to_local_model_definition_response(model) for model in guide.catalog_models
        ],
        safety_notes=guide.safety_notes,
        next_steps=guide.next_steps,
    )
