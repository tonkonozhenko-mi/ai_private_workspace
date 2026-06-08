from dataclasses import dataclass

from app.core.domain.workspace_models_dashboard_summary import (
    WorkspaceModelsDashboardSummary,
)
from app.core.use_cases.get_workspace_models_dashboard import (
    GetWorkspaceModelsDashboardInput,
    GetWorkspaceModelsDashboardUseCase,
    WorkspaceModelsDashboardNotFoundError,
)


SUMMARY_NOTES = [
    "Workspace models dashboard summary is read-only.",
    "Use the detailed workspace models dashboard for full diagnostics.",
]


@dataclass(frozen=True)
class GetWorkspaceModelsDashboardSummaryInput:
    workspace_id: str


class WorkspaceModelsDashboardSummaryNotFoundError(ValueError):
    pass


class GetWorkspaceModelsDashboardSummaryUseCase:
    def __init__(
        self,
        dashboard_use_case: GetWorkspaceModelsDashboardUseCase,
    ) -> None:
        self.dashboard_use_case = dashboard_use_case

    def execute(
        self,
        request: GetWorkspaceModelsDashboardSummaryInput,
    ) -> WorkspaceModelsDashboardSummary:
        try:
            dashboard = self.dashboard_use_case.execute(
                GetWorkspaceModelsDashboardInput(workspace_id=request.workspace_id)
            )
        except WorkspaceModelsDashboardNotFoundError as exc:
            raise WorkspaceModelsDashboardSummaryNotFoundError(str(exc)) from exc

        top_recommendation = (
            dashboard.recommendations.recommendations[0]
            if dashboard.recommendations.recommendations
            else None
        )
        return WorkspaceModelsDashboardSummary(
            workspace_id=dashboard.workspace_id,
            overall_status=dashboard.overall_status,
            primary_next_action_id=dashboard.primary_next_action_id,
            primary_next_action_title=dashboard.primary_next_action_title,
            selected_llm=self._selected_identity(
                dashboard.selected_llm_provider,
                dashboard.selected_llm_model,
            ),
            selected_embedding=self._selected_identity(
                dashboard.selected_embedding_provider,
                dashboard.selected_embedding_model,
            ),
            active_llm=self._active_identity(
                dashboard.usage_plan.active_llm_provider,
                dashboard.usage_plan.active_llm_model,
            ),
            active_embedding=self._active_identity(
                dashboard.usage_plan.active_embedding_provider,
                dashboard.usage_plan.active_embedding_model,
            ),
            can_ask_with_selected_llm=(
                dashboard.usage_plan.can_ask_with_selected_llm
            ),
            can_search_with_selected_embedding=(
                dashboard.usage_plan.can_search_with_selected_embedding
            ),
            top_recommended_model=(
                self._active_identity(
                    top_recommendation.model.provider,
                    top_recommendation.model.model_name,
                )
                if top_recommendation is not None
                else None
            ),
            top_recommended_model_score=(
                top_recommendation.final_score
                if top_recommendation is not None
                else None
            ),
            performance_models_count=len(dashboard.performance_summary.items),
            warnings_count=self._warnings_count(dashboard),
            notes=list(SUMMARY_NOTES),
        )

    @staticmethod
    def _selected_identity(provider: str | None, model: str | None) -> str | None:
        if provider is None or model is None:
            return None
        return f"{provider}/{model}"

    @staticmethod
    def _active_identity(provider: str, model: str) -> str:
        return f"{provider}/{model}"

    @staticmethod
    def _warnings_count(dashboard) -> int:
        recommendation_warnings = sum(
            len(recommendation.warnings)
            for recommendation in dashboard.recommendations.recommendations
        )
        embedding_warnings = len(dashboard.embedding_indexing_plan.warnings)
        not_ready_capabilities = sum(
            capability.status != "ready"
            for capability in dashboard.usage_plan.capabilities
        )
        return recommendation_warnings + embedding_warnings + not_ready_capabilities
