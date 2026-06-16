from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry
from app.core.domain.model_experiment import (
    ModelExperimentCandidate,
    ModelExperimentPlan,
)
from app.core.ports.index_status_repository import IndexStatusRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort

SUPPORTED_EXPERIMENT_TYPE = "llm_comparison"
SHARED_CONTEXT_STRATEGY = "Use the same indexed workspace context for all LLM candidates."
ADVISORY_NOTE = (
    "This plan is advisory and does not call models, download models, change "
    "runtime settings, reindex, or mutate workspace data."
)
OVERRIDE_NOTE = (
    "Per-request LLM override supports fake and ollama candidates without changing "
    "active runtime settings or restarting the backend."
)
MEASUREMENT_NOTE = (
    "A future experiment run should measure answer quality, source grounding, "
    "quality warnings, and latency."
)


@dataclass(frozen=True)
class ModelExperimentCandidateInput:
    provider: str
    model: str


@dataclass(frozen=True)
class CreateModelExperimentPlanInput:
    workspace_id: str
    question: str
    candidates: list[ModelExperimentCandidateInput]
    experiment_type: str = SUPPORTED_EXPERIMENT_TYPE


class ModelExperimentPlanValidationError(ValueError):
    pass


class ModelExperimentPlanWorkspaceNotFoundError(ValueError):
    pass


class CreateModelExperimentPlanUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        index_status_repository: IndexStatusRepositoryPort,
        model_catalog_registry: ModelCatalogRegistry,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.index_status_repository = index_status_repository
        self.model_catalog_registry = model_catalog_registry

    def execute(
        self,
        request: CreateModelExperimentPlanInput,
    ) -> ModelExperimentPlan:
        workspace_id = request.workspace_id.strip()
        question = request.question.strip()
        experiment_type = request.experiment_type.strip().lower()
        self._validate(request, workspace_id, question, experiment_type)

        if self.workspace_repository.get(workspace_id) is None:
            raise ModelExperimentPlanWorkspaceNotFoundError("Workspace not found")

        index_status = self.index_status_repository.get(workspace_id)
        is_indexed = index_status is not None and index_status.status == "indexed"
        candidates = [self._candidate(candidate, is_indexed) for candidate in request.candidates]

        actions: list[str] = []
        if not is_indexed:
            actions.append("Index workspace first.")
        actions.extend(
            [
                "Ensure candidate models are installed locally.",
                "Use per-request LLM override to run supported candidates.",
                "Compare answer quality, source grounding, warnings, and latency.",
            ]
        )

        notes = [ADVISORY_NOTE, OVERRIDE_NOTE, MEASUREMENT_NOTE]
        if is_indexed:
            notes.append(
                "The saved workspace index can provide shared context to every "
                "LLM candidate without reindexing."
            )
        else:
            notes.append(
                "The workspace is not indexed, so shared RAG context is not yet "
                "available for comparison."
            )

        return ModelExperimentPlan(
            workspace_id=workspace_id,
            question=question,
            experiment_type=experiment_type,
            candidates=candidates,
            shared_context_strategy=SHARED_CONTEXT_STRATEGY,
            requires_reindex=False,
            can_compare_without_reindex=is_indexed,
            recommended_actions=actions,
            notes=notes,
        )

    @staticmethod
    def _validate(
        request: CreateModelExperimentPlanInput,
        workspace_id: str,
        question: str,
        experiment_type: str,
    ) -> None:
        if not workspace_id:
            raise ModelExperimentPlanValidationError("workspace_id is required")
        if not question:
            raise ModelExperimentPlanValidationError("Question is required")
        if experiment_type != SUPPORTED_EXPERIMENT_TYPE:
            raise ModelExperimentPlanValidationError(
                f"Unknown experiment type: {request.experiment_type}"
            )
        if not request.candidates:
            raise ModelExperimentPlanValidationError("At least one model candidate is required")
        for candidate in request.candidates:
            if not candidate.provider.strip():
                raise ModelExperimentPlanValidationError("Candidate provider is required")
            if not candidate.model.strip():
                raise ModelExperimentPlanValidationError("Candidate model is required")

    def _candidate(
        self,
        candidate: ModelExperimentCandidateInput,
        is_indexed: bool,
    ) -> ModelExperimentCandidate:
        provider = candidate.provider.strip().lower()
        model_name = candidate.model.strip()
        catalog_model = self._find_catalog_model(provider, model_name)
        provider_supported = provider in {"fake", "ollama"}
        warnings: list[str] = []

        if catalog_model is None:
            warnings.append("Model is not in catalog; validate metadata before experiment.")
        if provider == "ollama":
            warnings.append(
                "Ollama model installation is not verified; install it manually if needed."
            )
        elif provider == "fake":
            warnings.append("Fake LLM returns deterministic development/testing responses.")
        else:
            warnings.append(f"Provider {provider} requires a compatible LLM provider adapter.")
        if not is_indexed:
            warnings.append("Workspace is not indexed; shared context is unavailable.")

        return ModelExperimentCandidate(
            provider=provider,
            model=model_name,
            known_in_catalog=catalog_model is not None,
            display_name=(catalog_model.display_name if catalog_model is not None else None),
            model_type="llm",
            requires_reindex=False,
            requires_backend_restart=not provider_supported,
            warnings=warnings,
        )

    def _find_catalog_model(
        self,
        provider: str,
        model_name: str,
    ) -> LocalModelDefinition | None:
        return next(
            (
                model
                for model in self.model_catalog_registry.list_models()
                if model.model_type == "llm"
                and model.provider.lower() == provider.lower()
                and model.model_name.lower() == model_name.lower()
            ),
            None,
        )
