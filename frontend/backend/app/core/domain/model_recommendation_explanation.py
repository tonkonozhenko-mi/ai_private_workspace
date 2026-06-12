from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRecommendationExplanationSection:
    title: str
    bullets: list[str]


@dataclass(frozen=True)
class ModelRecommendationExplanation:
    workspace_id: str
    provider: str
    model: str
    model_type: str
    display_name: str | None
    summary: str
    sections: list[ModelRecommendationExplanationSection]
    recommended_actions: list[str]
    warnings: list[str]
    notes: list[str]
