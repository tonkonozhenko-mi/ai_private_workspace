from dataclasses import dataclass


@dataclass(frozen=True)
class ModelExperimentCandidateComparison:
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


@dataclass(frozen=True)
class ModelExperimentComparisonSummary:
    experiment_id: str
    workspace_id: str
    question: str
    experiment_status: str
    candidates_count: int
    completed_candidates_count: int
    failed_candidates_count: int
    recommended_candidate: str | None
    comparisons: list[ModelExperimentCandidateComparison]
    notes: list[str]
