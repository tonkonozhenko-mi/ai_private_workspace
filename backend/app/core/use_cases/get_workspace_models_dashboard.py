from dataclasses import dataclass

from app.core.domain.workspace_models_dashboard import WorkspaceModelsDashboard
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.get_model_performance_summary import (
    GetModelPerformanceSummaryInput,
    GetModelPerformanceSummaryUseCase,
)
from app.core.use_cases.get_selected_embedding_indexing_plan import (
    GetSelectedEmbeddingIndexingPlanInput,
    GetSelectedEmbeddingIndexingPlanUseCase,
)
from app.core.use_cases.get_selected_model_usage_plan import (
    GetSelectedModelUsagePlanInput,
    GetSelectedModelUsagePlanUseCase,
)
from app.core.use_cases.get_workspace_model_selection import (
    GetWorkspaceModelSelectionInput,
    GetWorkspaceModelSelectionUseCase,
)
from app.core.use_cases.get_workspace_model_selection_status import (
    GetWorkspaceModelSelectionStatusInput,
    GetWorkspaceModelSelectionStatusUseCase,
)
from app.core.use_cases.recommend_workspace_models import (
    RecommendWorkspaceModelsInput,
    RecommendWorkspaceModelsUseCase,
)

DASHBOARD_NOTES = [
    "Workspace models dashboard is read-only and does not change runtime settings.",
    "Model recommendations do not automatically select models.",
    "A supported selected LLM can be used through a per-request override.",
    (
        "A selected embedding requires active runtime and index compatibility "
        "before search can use it."
    ),
]


@dataclass(frozen=True)
class GetWorkspaceModelsDashboardInput:
    workspace_id: str
    laptop_profile_id: str = "balanced"
    task_type: str = "workspace_ask"
    model_type: str = "llm"


class WorkspaceModelsDashboardNotFoundError(ValueError):
    pass


class GetWorkspaceModelsDashboardUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        selection_use_case: GetWorkspaceModelSelectionUseCase,
        selection_status_use_case: GetWorkspaceModelSelectionStatusUseCase,
        usage_plan_use_case: GetSelectedModelUsagePlanUseCase,
        embedding_indexing_plan_use_case: GetSelectedEmbeddingIndexingPlanUseCase,
        recommendation_use_case: RecommendWorkspaceModelsUseCase,
        performance_summary_use_case: GetModelPerformanceSummaryUseCase,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.selection_use_case = selection_use_case
        self.selection_status_use_case = selection_status_use_case
        self.usage_plan_use_case = usage_plan_use_case
        self.embedding_indexing_plan_use_case = embedding_indexing_plan_use_case
        self.recommendation_use_case = recommendation_use_case
        self.performance_summary_use_case = performance_summary_use_case

    def execute(
        self,
        request: GetWorkspaceModelsDashboardInput,
    ) -> WorkspaceModelsDashboard:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceModelsDashboardNotFoundError("Workspace not found")

        selection = self.selection_use_case.execute(
            GetWorkspaceModelSelectionInput(workspace_id=request.workspace_id)
        )
        selection_status = self.selection_status_use_case.execute(
            GetWorkspaceModelSelectionStatusInput(workspace_id=request.workspace_id)
        )
        usage_plan = self.usage_plan_use_case.execute(
            GetSelectedModelUsagePlanInput(workspace_id=request.workspace_id)
        )
        embedding_indexing_plan = self.embedding_indexing_plan_use_case.execute(
            GetSelectedEmbeddingIndexingPlanInput(workspace_id=request.workspace_id)
        )
        recommendations = self.recommendation_use_case.execute(
            RecommendWorkspaceModelsInput(
                workspace_id=request.workspace_id,
                assistant_profile_id=workspace.assistant_mode,
                laptop_profile_id=request.laptop_profile_id,
                task_type=request.task_type,
                model_type=request.model_type,
            )
        )
        performance_summary = self.performance_summary_use_case.execute(
            GetModelPerformanceSummaryInput(workspace_id=request.workspace_id)
        )
        overall_status = self._overall_status(
            selection=selection,
            usage_plan=usage_plan,
            embedding_plan=embedding_indexing_plan,
        )
        action_id, action_title = self._primary_next_action(
            selection=selection,
            usage_plan=usage_plan,
            embedding_plan=embedding_indexing_plan,
        )

        return WorkspaceModelsDashboard(
            workspace_id=request.workspace_id,
            selected_llm_provider=(
                selection.selected_llm.provider if selection.selected_llm else None
            ),
            selected_llm_model=(selection.selected_llm.model if selection.selected_llm else None),
            selected_embedding_provider=(
                selection.selected_embedding.provider if selection.selected_embedding else None
            ),
            selected_embedding_model=(
                selection.selected_embedding.model if selection.selected_embedding else None
            ),
            overall_status=overall_status,
            primary_next_action_id=action_id,
            primary_next_action_title=action_title,
            selection=selection,
            selection_status=selection_status,
            usage_plan=usage_plan,
            embedding_indexing_plan=embedding_indexing_plan,
            recommendations=recommendations,
            performance_summary=performance_summary,
            notes=list(DASHBOARD_NOTES),
        )

    @staticmethod
    def _overall_status(*, selection, usage_plan, embedding_plan) -> str:
        if selection.selected_llm is None or selection.selected_embedding is None:
            return "needs_model_selection"
        # A reindex need (including an index built by a now-different search model)
        # takes priority over "ready", so the rebuild prompt appears exactly when
        # it is needed — and not otherwise.
        if embedding_plan.plan_status == "runtime_mismatch":
            return "needs_embedding_runtime"
        if embedding_plan.plan_status == "needs_index":
            return "needs_context_index"
        if usage_plan.can_use_selected_models_fully:
            return "ready"
        if usage_plan.can_ask_with_selected_llm:
            return "usable_with_selected_llm"
        return "needs_attention"

    @staticmethod
    def _primary_next_action(*, selection, usage_plan, embedding_plan):
        if selection.selected_llm is None:
            return "select_llm_model", "Select an LLM model"
        if selection.selected_embedding is None:
            return "select_embedding_model", "Select an embedding model"
        if embedding_plan.plan_status == "runtime_mismatch":
            return (
                "restart_backend_for_embedding",
                "Restart backend for selected search model",
            )
        if embedding_plan.plan_status == "needs_index":
            return "reindex_workspace", "Build context with selected search model"
        if usage_plan.can_ask_with_selected_llm:
            return "ask_with_selected_llm", "Ask using selected LLM"
        return "review_model_selection", "Review model selection"
