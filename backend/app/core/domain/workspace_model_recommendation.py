from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition


@dataclass(frozen=True)
class WorkspaceModelRecommendation:
    model: LocalModelDefinition
    catalog_score: int
    performance_score: int | None
    final_score: int
    reasons: list[str]
    warnings: list[str]
    historical_signals: dict[str, str]


@dataclass(frozen=True)
class WorkspaceModelRecommendationResult:
    workspace_id: str
    assistant_profile_id: str
    laptop_profile_id: str
    task_type: str
    model_type: str
    recommendations: list[WorkspaceModelRecommendation]
    notes: list[str]
