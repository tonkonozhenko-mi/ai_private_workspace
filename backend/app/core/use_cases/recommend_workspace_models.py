from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.domain.model_performance import ModelPerformanceItem
from app.core.domain.workspace_model_recommendation import (
    WorkspaceModelRecommendation,
    WorkspaceModelRecommendationResult,
)
from app.core.ports.model_experiment_rating_repository import (
    ModelExperimentRatingRepositoryPort,
)
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.get_model_performance_summary import (
    GetModelPerformanceSummaryInput,
    GetModelPerformanceSummaryUseCase,
)
from app.core.use_cases.recommend_models import (
    RecommendModelsInput,
    RecommendModelsUseCase,
)


NO_HISTORY_WARNING = "No workspace performance history for this model yet."
RECOMMENDATION_NOTES = [
    "Recommendations combine static catalog scoring with workspace performance history.",
    "Historical scores are deterministic signals, not a semantic quality evaluation.",
    "Recommendations do not change runtime settings or select a model automatically.",
]


@dataclass(frozen=True)
class RecommendWorkspaceModelsInput:
    workspace_id: str
    assistant_profile_id: str | None
    laptop_profile_id: str
    task_type: str
    model_type: str


class WorkspaceModelRecommendationNotFoundError(ValueError):
    pass


class RecommendWorkspaceModelsUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        model_experiment_repository: ModelExperimentRepositoryPort,
        rating_repository: ModelExperimentRatingRepositoryPort,
        model_catalog_registry: ModelCatalogRegistry,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.model_experiment_repository = model_experiment_repository
        self.rating_repository = rating_repository
        self.model_catalog_registry = model_catalog_registry

    def execute(
        self,
        request: RecommendWorkspaceModelsInput,
    ) -> WorkspaceModelRecommendationResult:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise WorkspaceModelRecommendationNotFoundError("Workspace not found")

        assistant_profile_id = request.assistant_profile_id or workspace.assistant_mode
        catalog_result = RecommendModelsUseCase(
            model_catalog_registry=self.model_catalog_registry
        ).execute(
            RecommendModelsInput(
                assistant_profile_id=assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                task_type=request.task_type,
                model_type=request.model_type,
            )
        )
        performance = GetModelPerformanceSummaryUseCase(
            workspace_repository=self.workspace_repository,
            model_experiment_repository=self.model_experiment_repository,
            rating_repository=self.rating_repository,
        ).execute(
            GetModelPerformanceSummaryInput(workspace_id=request.workspace_id)
        )
        performance_by_model = {
            (item.provider, item.model): item
            for item in performance.items
        }

        recommendations = [
            self._merge_recommendation(
                recommendation.model,
                recommendation.score,
                recommendation.reasons,
                recommendation.warnings,
                performance_by_model.get(
                    (
                        recommendation.model.provider,
                        recommendation.model.model_name,
                    )
                ),
            )
            for recommendation in catalog_result.recommendations
        ]
        recommendations.sort(
            key=lambda recommendation: (
                -recommendation.final_score,
                recommendation.model.id,
            )
        )
        return WorkspaceModelRecommendationResult(
            workspace_id=workspace.id,
            assistant_profile_id=assistant_profile_id,
            laptop_profile_id=catalog_result.laptop_profile_id,
            task_type=catalog_result.task_type,
            model_type=catalog_result.model_type,
            recommendations=recommendations,
            notes=list(RECOMMENDATION_NOTES),
        )

    @classmethod
    def _merge_recommendation(
        cls,
        model: LocalModelDefinition,
        catalog_score: int,
        catalog_reasons: list[str],
        catalog_warnings: list[str],
        performance: ModelPerformanceItem | None,
    ) -> WorkspaceModelRecommendation:
        reasons = list(catalog_reasons)
        warnings = list(catalog_warnings)
        final_score = catalog_score

        if performance is None:
            warnings.append(NO_HISTORY_WARNING)
            return WorkspaceModelRecommendation(
                model=model,
                catalog_score=catalog_score,
                performance_score=None,
                final_score=final_score,
                reasons=reasons,
                warnings=warnings,
                historical_signals=cls._historical_signals(None),
            )

        final_score += performance.score
        reasons.append(
            f"{performance.score:+d}: Workspace performance summary score."
        )
        if performance.average_rating is not None and performance.average_rating >= 4:
            final_score += 10
            reasons.append("+10: Workspace average user rating is at least 4.")
        if performance.preferred_votes > 0:
            final_score += 10
            reasons.append("+10: Model has workspace preferred votes.")
        if performance.failed_runs_count > performance.completed_runs_count:
            final_score -= 10
            reasons.append("-10: Failed runs outnumber completed runs.")

        return WorkspaceModelRecommendation(
            model=model,
            catalog_score=catalog_score,
            performance_score=performance.score,
            final_score=final_score,
            reasons=reasons,
            warnings=warnings,
            historical_signals=cls._historical_signals(performance),
        )

    @staticmethod
    def _historical_signals(
        performance: ModelPerformanceItem | None,
    ) -> dict[str, str]:
        if performance is None:
            return {
                "experiments_count": "0",
                "ratings_count": "0",
                "average_rating": "not_available",
                "preferred_votes": "0",
                "average_latency_ms": "not_available",
            }
        return {
            "experiments_count": str(performance.experiments_count),
            "ratings_count": str(performance.ratings_count),
            "average_rating": (
                str(performance.average_rating)
                if performance.average_rating is not None
                else "not_available"
            ),
            "preferred_votes": str(performance.preferred_votes),
            "average_latency_ms": (
                str(performance.average_latency_ms)
                if performance.average_latency_ms is not None
                else "not_available"
            ),
        }
