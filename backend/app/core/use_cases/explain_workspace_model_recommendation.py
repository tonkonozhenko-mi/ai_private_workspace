from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.domain.model_performance import ModelPerformanceItem
from app.core.domain.model_recommendation_explanation import (
    ModelRecommendationExplanation,
    ModelRecommendationExplanationSection,
)
from app.core.domain.workspace_model_recommendation import WorkspaceModelRecommendation
from app.core.ports.model_experiment_rating_repository import (
    ModelExperimentRatingRepositoryPort,
)
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.get_model_performance_summary import (
    GetModelPerformanceSummaryInput,
    GetModelPerformanceSummaryUseCase,
)
from app.core.use_cases.recommend_workspace_models import (
    RecommendWorkspaceModelsInput,
    RecommendWorkspaceModelsUseCase,
)

STATIC_METADATA_WARNING = (
    "Model metadata is static and should be validated against local runtime before use."
)
RUNTIME_NOT_VERIFIED_WARNING = (
    "Model availability has not been verified against the installed local runtime."
)
UNKNOWN_MODEL_WARNING = "Model is not present in the current local model catalog."
NO_HISTORY_WARNING = "No workspace performance history for this model yet."
FAKE_MODEL_WARNING = "Fake model is intended for development/testing only."
EXPLANATION_NOTES = [
    "This explanation is deterministic and uses catalog plus workspace history.",
    "It does not verify installed models, call providers, or change runtime settings.",
]


@dataclass(frozen=True)
class ExplainWorkspaceModelRecommendationInput:
    workspace_id: str
    provider: str
    model: str
    model_type: str
    laptop_profile_id: str
    task_type: str
    assistant_profile_id: str | None = None


class ModelRecommendationExplanationNotFoundError(ValueError):
    pass


class ExplainWorkspaceModelRecommendationUseCase:
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
        request: ExplainWorkspaceModelRecommendationInput,
    ) -> ModelRecommendationExplanation:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise ModelRecommendationExplanationNotFoundError("Workspace not found")

        provider = request.provider.strip().lower()
        model_name = request.model.strip()
        model_type = request.model_type.strip().lower()
        assistant_profile_id = request.assistant_profile_id or workspace.assistant_mode

        recommendation_result = RecommendWorkspaceModelsUseCase(
            workspace_repository=self.workspace_repository,
            model_experiment_repository=self.model_experiment_repository,
            rating_repository=self.rating_repository,
            model_catalog_registry=self.model_catalog_registry,
        ).execute(
            RecommendWorkspaceModelsInput(
                workspace_id=workspace.id,
                assistant_profile_id=assistant_profile_id,
                laptop_profile_id=request.laptop_profile_id,
                task_type=request.task_type,
                model_type=model_type,
            )
        )
        performance_summary = GetModelPerformanceSummaryUseCase(
            workspace_repository=self.workspace_repository,
            model_experiment_repository=self.model_experiment_repository,
            rating_repository=self.rating_repository,
        ).execute(GetModelPerformanceSummaryInput(workspace_id=workspace.id))
        catalog_model = self._find_catalog_model(provider, model_name, model_type)
        recommendation = self._find_recommendation(
            recommendation_result.recommendations,
            provider,
            model_name,
        )
        performance = self._find_performance(
            performance_summary.items,
            provider,
            model_name,
        )
        warnings = self._warnings(
            provider=provider,
            catalog_model=catalog_model,
            recommendation=recommendation,
            performance=performance,
        )

        return ModelRecommendationExplanation(
            workspace_id=workspace.id,
            provider=provider,
            model=model_name,
            model_type=model_type,
            display_name=catalog_model.display_name if catalog_model else None,
            summary=self._summary(
                provider=provider,
                catalog_model=catalog_model,
                recommendation=recommendation,
                performance=performance,
            ),
            sections=[
                self._catalog_fit_section(
                    catalog_model=catalog_model,
                    recommendation=recommendation,
                    assistant_profile_id=assistant_profile_id,
                    laptop_profile_id=request.laptop_profile_id,
                ),
                self._workspace_history_section(performance),
                self._switching_impact_section(model_type),
                ModelRecommendationExplanationSection(
                    title="Risks and limitations",
                    bullets=warnings,
                ),
            ],
            recommended_actions=self._recommended_actions(
                provider=provider,
                model_name=model_name,
                model_type=model_type,
                catalog_model=catalog_model,
                performance=performance,
            ),
            warnings=warnings,
            notes=list(EXPLANATION_NOTES),
        )

    def _find_catalog_model(
        self,
        provider: str,
        model_name: str,
        model_type: str,
    ) -> LocalModelDefinition | None:
        return next(
            (
                model
                for model in self.model_catalog_registry.list_models()
                if model.provider.lower() == provider
                and model.model_name.lower() == model_name.lower()
                and model.model_type == model_type
            ),
            None,
        )

    @staticmethod
    def _find_recommendation(
        recommendations: list[WorkspaceModelRecommendation],
        provider: str,
        model_name: str,
    ) -> WorkspaceModelRecommendation | None:
        return next(
            (
                recommendation
                for recommendation in recommendations
                if recommendation.model.provider.lower() == provider
                and recommendation.model.model_name.lower() == model_name.lower()
            ),
            None,
        )

    @staticmethod
    def _find_performance(
        items: list[ModelPerformanceItem],
        provider: str,
        model_name: str,
    ) -> ModelPerformanceItem | None:
        return next(
            (
                item
                for item in items
                if item.provider.lower() == provider and item.model.lower() == model_name.lower()
            ),
            None,
        )

    @staticmethod
    def _summary(
        *,
        provider: str,
        catalog_model: LocalModelDefinition | None,
        recommendation: WorkspaceModelRecommendation | None,
        performance: ModelPerformanceItem | None,
    ) -> str:
        if provider == "fake":
            return (
                "This model is mainly for development/testing and remains visible "
                "for deterministic workflows."
            )
        if catalog_model is None:
            return (
                "This model is unknown to the current catalog, so its fit and runtime "
                "requirements cannot be fully verified."
            )
        if performance is None:
            return (
                "This model is recommended mostly from catalog metadata because no "
                "workspace performance history is available yet."
            )
        if recommendation is not None and recommendation.final_score >= 80:
            return (
                "This model is strongly recommended because catalog fit and workspace "
                "history both provide positive signals."
            )
        return (
            "This model recommendation combines catalog metadata with available "
            "workspace performance history."
        )

    @staticmethod
    def _catalog_fit_section(
        *,
        catalog_model: LocalModelDefinition | None,
        recommendation: WorkspaceModelRecommendation | None,
        assistant_profile_id: str,
        laptop_profile_id: str,
    ) -> ModelRecommendationExplanationSection:
        if catalog_model is None:
            return ModelRecommendationExplanationSection(
                title="Catalog fit",
                bullets=["Model is not present in the current local model catalog."],
            )

        bullets = [
            (
                f"Assistant profile {assistant_profile_id} is recommended."
                if assistant_profile_id in catalog_model.recommended_for_profiles
                else f"Assistant profile {assistant_profile_id} is not a catalog match."
            ),
            (
                f"Laptop profile {laptop_profile_id} is recommended."
                if laptop_profile_id in catalog_model.recommended_laptop_profiles
                else f"Laptop profile {laptop_profile_id} is not a catalog match."
            ),
            f"Quality tier: {catalog_model.quality_tier}.",
            f"Speed tier: {catalog_model.speed_tier}.",
            "Capabilities: " + ", ".join(catalog_model.capabilities) + ".",
        ]
        if recommendation is not None:
            bullets.append(f"Catalog score: {recommendation.catalog_score}.")
            bullets.append(f"Workspace-aware final score: {recommendation.final_score}.")
        return ModelRecommendationExplanationSection(
            title="Catalog fit",
            bullets=bullets,
        )

    @staticmethod
    def _workspace_history_section(
        performance: ModelPerformanceItem | None,
    ) -> ModelRecommendationExplanationSection:
        if performance is None:
            return ModelRecommendationExplanationSection(
                title="Workspace history",
                bullets=["No workspace performance history is available for this model."],
            )
        bullets = [
            f"Experiments: {performance.experiments_count}.",
            f"Ratings: {performance.ratings_count}.",
            (
                f"Average rating: {performance.average_rating}."
                if performance.average_rating is not None
                else "Average rating: not available."
            ),
            f"Preferred votes: {performance.preferred_votes}.",
        ]
        if performance.common_tags:
            bullets.append("Common tags: " + ", ".join(performance.common_tags) + ".")
        return ModelRecommendationExplanationSection(
            title="Workspace history",
            bullets=bullets,
        )

    @staticmethod
    def _switching_impact_section(
        model_type: str,
    ) -> ModelRecommendationExplanationSection:
        if model_type == "embedding":
            bullets = [
                "Switching embedding models requires workspace reindexing.",
                "A new dimension-aware vector collection may be required.",
            ]
        else:
            bullets = [
                "Switching LLMs does not require workspace reindexing.",
                "Existing retrieved context and vector collections remain usable.",
            ]
        return ModelRecommendationExplanationSection(
            title="Switching impact",
            bullets=bullets,
        )

    @staticmethod
    def _warnings(
        *,
        provider: str,
        catalog_model: LocalModelDefinition | None,
        recommendation: WorkspaceModelRecommendation | None,
        performance: ModelPerformanceItem | None,
    ) -> list[str]:
        warnings = list(recommendation.warnings if recommendation else [])
        warnings.extend([STATIC_METADATA_WARNING, RUNTIME_NOT_VERIFIED_WARNING])
        if catalog_model is None:
            warnings.append(UNKNOWN_MODEL_WARNING)
        if provider == "fake":
            warnings.append(FAKE_MODEL_WARNING)
        if performance is None:
            warnings.append(NO_HISTORY_WARNING)
        return list(dict.fromkeys(warnings))

    @staticmethod
    def _recommended_actions(
        *,
        provider: str,
        model_name: str,
        model_type: str,
        catalog_model: LocalModelDefinition | None,
        performance: ModelPerformanceItem | None,
    ) -> list[str]:
        actions: list[str] = []
        if catalog_model is None:
            actions.append("Validate model metadata before use.")
        if provider == "ollama":
            actions.append(f"Ensure Ollama model {model_name} is installed locally.")
        elif provider not in {"fake", "ollama"}:
            actions.append(f"Configure a compatible provider adapter for {provider}.")
        if model_type == "embedding":
            actions.append("Review the model switching plan before reindexing.")
        else:
            actions.append(
                "Run a model experiment comparing this LLM with the current/default model."
            )
        if performance is None:
            actions.append("Run a model experiment and rate the answer.")
        return actions
