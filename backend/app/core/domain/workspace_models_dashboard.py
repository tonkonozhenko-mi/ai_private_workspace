from dataclasses import dataclass

from app.core.domain.model_performance import ModelPerformanceSummary
from app.core.domain.selected_embedding_indexing_plan import (
    SelectedEmbeddingIndexingPlan,
)
from app.core.domain.selected_model_usage_plan import SelectedModelUsagePlan
from app.core.domain.workspace_model_recommendation import (
    WorkspaceModelRecommendationResult,
)
from app.core.domain.workspace_model_selection import WorkspaceModelSelection
from app.core.domain.workspace_model_selection_status import (
    WorkspaceModelSelectionStatus,
)


@dataclass(frozen=True)
class WorkspaceModelsDashboard:
    workspace_id: str
    selected_llm_provider: str | None
    selected_llm_model: str | None
    selected_embedding_provider: str | None
    selected_embedding_model: str | None
    overall_status: str
    primary_next_action_id: str | None
    primary_next_action_title: str | None
    selection: WorkspaceModelSelection
    selection_status: WorkspaceModelSelectionStatus
    usage_plan: SelectedModelUsagePlan
    embedding_indexing_plan: SelectedEmbeddingIndexingPlan
    recommendations: WorkspaceModelRecommendationResult
    performance_summary: ModelPerformanceSummary
    notes: list[str]
