from pydantic import BaseModel, Field

from app.core.domain.model_experiment_run import (
    ModelExperimentCandidateResult,
    ModelExperimentRun,
)


class ModelExperimentRunCandidateRequest(BaseModel):
    provider: str
    model: str


class ModelExperimentAttachedDocumentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=400_000)


class RunModelExperimentRequest(BaseModel):
    workspace_id: str
    question: str
    experiment_type: str = "llm_comparison"
    candidates: list[ModelExperimentRunCandidateRequest]
    limit: int = Field(default=3, ge=1, le=50)
    attached_documents: list[ModelExperimentAttachedDocumentRequest] = Field(
        default_factory=list, max_length=6
    )


class ModelExperimentCandidateResultResponse(BaseModel):
    provider: str
    model: str
    status: str
    answer: str | None
    error: str | None
    llm_provider: str
    llm_model: str
    used_context_chunks: int
    sources_count: int
    quality_warnings_count: int
    latency_ms: int | None


class ModelExperimentRunResponse(BaseModel):
    id: str
    workspace_id: str
    question: str
    experiment_type: str
    status: str
    created_at: str
    completed_at: str | None
    shared_context_sources_count: int
    candidates: list[ModelExperimentCandidateResultResponse]
    notes: list[str]


def to_model_experiment_candidate_result_response(
    candidate: ModelExperimentCandidateResult,
) -> ModelExperimentCandidateResultResponse:
    return ModelExperimentCandidateResultResponse(
        provider=candidate.provider,
        model=candidate.model,
        status=candidate.status,
        answer=candidate.answer,
        error=candidate.error,
        llm_provider=candidate.llm_provider,
        llm_model=candidate.llm_model,
        used_context_chunks=candidate.used_context_chunks,
        sources_count=candidate.sources_count,
        quality_warnings_count=candidate.quality_warnings_count,
        latency_ms=candidate.latency_ms,
    )


def to_model_experiment_run_response(
    run: ModelExperimentRun,
) -> ModelExperimentRunResponse:
    return ModelExperimentRunResponse(
        id=run.id,
        workspace_id=run.workspace_id,
        question=run.question,
        experiment_type=run.experiment_type,
        status=run.status,
        created_at=run.created_at,
        completed_at=run.completed_at,
        shared_context_sources_count=run.shared_context_sources_count,
        candidates=[
            to_model_experiment_candidate_result_response(candidate)
            for candidate in run.candidates
        ],
        notes=run.notes,
    )
