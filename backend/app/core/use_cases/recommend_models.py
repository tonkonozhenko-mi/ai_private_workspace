from dataclasses import dataclass

from app.core.domain.assistant_profile_registry import AssistantProfileRegistry
from app.core.domain.laptop_profile_registry import LaptopProfileRegistry
from app.core.domain.model_catalog import (
    LocalModelDefinition,
    ModelRecommendation,
    ModelRecommendationResult,
)
from app.core.domain.model_catalog_registry import ModelCatalogRegistry


ALLOWED_MODEL_TYPES = {"llm", "embedding"}
STATIC_METADATA_WARNING = (
    "Model metadata is static and should be validated against local runtime before use."
)


@dataclass(frozen=True)
class RecommendModelsInput:
    assistant_profile_id: str
    laptop_profile_id: str
    task_type: str
    model_type: str


class ModelRecommendationValidationError(ValueError):
    pass


class RecommendModelsUseCase:
    def __init__(
        self,
        model_catalog_registry: ModelCatalogRegistry | None = None,
        assistant_profile_registry: AssistantProfileRegistry | None = None,
        laptop_profile_registry: LaptopProfileRegistry | None = None,
    ) -> None:
        self.model_catalog_registry = model_catalog_registry or ModelCatalogRegistry()
        self.assistant_profile_registry = (
            assistant_profile_registry or AssistantProfileRegistry()
        )
        self.laptop_profile_registry = laptop_profile_registry or LaptopProfileRegistry()

    def execute(self, request: RecommendModelsInput) -> ModelRecommendationResult:
        self._validate(request)
        model_type = request.model_type.lower()
        recommendations = [
            self._recommendation(
                model=model,
                assistant_profile_id=request.assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                requested_model_type=model_type,
            )
            for model in self.model_catalog_registry.list_models()
        ]
        recommendations.sort(
            key=lambda recommendation: (
                -recommendation.score,
                recommendation.model.id,
            )
        )

        return ModelRecommendationResult(
            assistant_profile_id=request.assistant_profile_id,
            laptop_profile_id=request.laptop_profile_id,
            task_type=request.task_type,
            model_type=model_type,
            recommendations=recommendations,
        )

    def _validate(self, request: RecommendModelsInput) -> None:
        assistant_profile_ids = {
            profile.id for profile in self.assistant_profile_registry.list_profiles()
        }
        if request.assistant_profile_id not in assistant_profile_ids:
            raise ModelRecommendationValidationError(
                f"Unknown assistant profile: {request.assistant_profile_id}"
            )
        if self.laptop_profile_registry.find_profile(request.laptop_profile_id) is None:
            raise ModelRecommendationValidationError(
                f"Unknown laptop profile: {request.laptop_profile_id}"
            )
        if request.model_type.lower() not in ALLOWED_MODEL_TYPES:
            raise ModelRecommendationValidationError(
                f"Unknown model type: {request.model_type}"
            )

    @staticmethod
    def _recommendation(
        model: LocalModelDefinition,
        assistant_profile_id: str,
        laptop_profile_id: str,
        requested_model_type: str,
    ) -> ModelRecommendation:
        score = 0
        reasons: list[str] = []
        warnings = [STATIC_METADATA_WARNING]

        if model.model_type == requested_model_type:
            score += 30
            reasons.append(f"Matches requested model type: {requested_model_type}.")
        else:
            score -= 30
            warnings.append(
                f"Model type {model.model_type} does not match requested type "
                f"{requested_model_type}."
            )

        if assistant_profile_id in model.recommended_for_profiles:
            score += 20
            reasons.append(f"Recommended for assistant profile: {assistant_profile_id}.")

        if laptop_profile_id in model.recommended_laptop_profiles:
            score += 20
            reasons.append(f"Recommended for laptop profile: {laptop_profile_id}.")
        else:
            score -= 20
            if laptop_profile_id == "low_power":
                warnings.append("Model may be heavy for low-power laptops.")
            else:
                warnings.append(
                    f"Model is not recommended for laptop profile: {laptop_profile_id}."
                )

        if model.local_only:
            score += 10
            reasons.append("Runs through a local-only provider.")

        if model.quality_tier == "strong":
            score += 10
            reasons.append("Catalog quality tier is strong.")
        elif model.quality_tier == "good":
            score += 5
            reasons.append("Catalog quality tier is good.")

        if laptop_profile_id == "low_power" and model.speed_tier == "fast":
            score += 5
            reasons.append("Fast speed tier suits low-power laptops.")

        if model.provider == "fake":
            warnings.append("Fake model is intended for development/testing only.")

        return ModelRecommendation(
            model=model,
            score=score,
            reasons=reasons,
            warnings=warnings,
        )
