from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_fit import assess_model_fit


@dataclass(frozen=True)
class GuidedModelSetupOption:
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
    estimated_size: str | None
    fit: str | None
    fit_label: str | None
    notes: list[str]


@dataclass(frozen=True)
class GuidedModelSetupSection:
    model_type: str
    title: str
    purpose: str
    recommendation_summary: str
    custom_model_hint: str
    options: list[GuidedModelSetupOption]


@dataclass(frozen=True)
class GuidedModelSetupGuide:
    workspace_id: str
    title: str
    summary: str
    llm: GuidedModelSetupSection
    embedding: GuidedModelSetupSection
    packaging_notes: list[str]
    safety_notes: list[str]


def to_guided_model_option(
    model: LocalModelDefinition,
    *,
    recommendation_label: str,
    recommended: bool,
    total_ram_gb: float | None = None,
) -> GuidedModelSetupOption:
    fit, fit_label = assess_model_fit(model.estimated_size, total_ram_gb)
    return GuidedModelSetupOption(
        provider=model.provider,
        model=model.model_name,
        model_type=model.model_type,
        display_name=model.display_name,
        description=model.description,
        recommendation_label=recommendation_label,
        recommended=recommended,
        local_only=model.local_only,
        quality_tier=model.quality_tier,
        speed_tier=model.speed_tier,
        estimated_size=model.estimated_size,
        fit=fit,
        fit_label=fit_label,
        notes=list(model.notes),
    )
