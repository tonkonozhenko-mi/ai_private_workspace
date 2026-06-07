from dataclasses import dataclass


@dataclass(frozen=True)
class LocalModelDefinition:
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


@dataclass(frozen=True)
class ModelCatalogWarning:
    code: str
    message: str
    source: str | None


@dataclass(frozen=True)
class ModelCatalogResult:
    models: list[LocalModelDefinition]
    warnings: list[ModelCatalogWarning]


@dataclass(frozen=True)
class ModelRecommendation:
    model: LocalModelDefinition
    score: int
    reasons: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class ModelRecommendationResult:
    assistant_profile_id: str
    laptop_profile_id: str
    task_type: str
    model_type: str
    recommendations: list[ModelRecommendation]
