from pydantic import BaseModel

from app.core.domain.model_experiment import (
    ModelExperimentCandidate,
    ModelExperimentPlan,
)


class ModelExperimentCandidateRequest(BaseModel):
    provider: str
    model: str


class CreateModelExperimentPlanRequest(BaseModel):
    workspace_id: str
    question: str
    candidates: list[ModelExperimentCandidateRequest]
    experiment_type: str = "llm_comparison"


class ModelExperimentCandidateResponse(BaseModel):
    provider: str
    model: str
    known_in_catalog: bool
    display_name: str | None
    model_type: str
    requires_reindex: bool
    requires_backend_restart: bool
    warnings: list[str]


class ModelExperimentPlanResponse(BaseModel):
    workspace_id: str
    question: str
    experiment_type: str
    candidates: list[ModelExperimentCandidateResponse]
    shared_context_strategy: str
    requires_reindex: bool
    can_compare_without_reindex: bool
    recommended_actions: list[str]
    notes: list[str]


def to_model_experiment_candidate_response(
    candidate: ModelExperimentCandidate,
) -> ModelExperimentCandidateResponse:
    return ModelExperimentCandidateResponse(
        provider=candidate.provider,
        model=candidate.model,
        known_in_catalog=candidate.known_in_catalog,
        display_name=candidate.display_name,
        model_type=candidate.model_type,
        requires_reindex=candidate.requires_reindex,
        requires_backend_restart=candidate.requires_backend_restart,
        warnings=candidate.warnings,
    )


def to_model_experiment_plan_response(
    plan: ModelExperimentPlan,
) -> ModelExperimentPlanResponse:
    return ModelExperimentPlanResponse(
        workspace_id=plan.workspace_id,
        question=plan.question,
        experiment_type=plan.experiment_type,
        candidates=[
            to_model_experiment_candidate_response(candidate)
            for candidate in plan.candidates
        ],
        shared_context_strategy=plan.shared_context_strategy,
        requires_reindex=plan.requires_reindex,
        can_compare_without_reindex=plan.can_compare_without_reindex,
        recommended_actions=plan.recommended_actions,
        notes=plan.notes,
    )
