from pydantic import BaseModel

from app.core.domain.model_experiment_comparison import (
    ModelExperimentCandidateComparison,
    ModelExperimentComparisonSummary,
)


class ModelExperimentCandidateComparisonResponse(BaseModel):
    provider: str
    model: str
    status: str
    answer_length: int
    latency_ms: int | None
    sources_count: int
    quality_warnings_count: int
    score: int
    score_reasons: list[str]
    warnings: list[str]


class ModelExperimentComparisonSummaryResponse(BaseModel):
    experiment_id: str
    workspace_id: str
    question: str
    experiment_status: str
    candidates_count: int
    completed_candidates_count: int
    failed_candidates_count: int
    recommended_candidate: str | None
    comparisons: list[ModelExperimentCandidateComparisonResponse]
    notes: list[str]


def to_model_experiment_candidate_comparison_response(
    comparison: ModelExperimentCandidateComparison,
) -> ModelExperimentCandidateComparisonResponse:
    return ModelExperimentCandidateComparisonResponse(
        provider=comparison.provider,
        model=comparison.model,
        status=comparison.status,
        answer_length=comparison.answer_length,
        latency_ms=comparison.latency_ms,
        sources_count=comparison.sources_count,
        quality_warnings_count=comparison.quality_warnings_count,
        score=comparison.score,
        score_reasons=comparison.score_reasons,
        warnings=comparison.warnings,
    )


def to_model_experiment_comparison_summary_response(
    summary: ModelExperimentComparisonSummary,
) -> ModelExperimentComparisonSummaryResponse:
    return ModelExperimentComparisonSummaryResponse(
        experiment_id=summary.experiment_id,
        workspace_id=summary.workspace_id,
        question=summary.question,
        experiment_status=summary.experiment_status,
        candidates_count=summary.candidates_count,
        completed_candidates_count=summary.completed_candidates_count,
        failed_candidates_count=summary.failed_candidates_count,
        recommended_candidate=summary.recommended_candidate,
        comparisons=[
            to_model_experiment_candidate_comparison_response(comparison)
            for comparison in summary.comparisons
        ],
        notes=summary.notes,
    )
