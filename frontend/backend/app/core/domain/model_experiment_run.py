from dataclasses import dataclass


@dataclass(frozen=True)
class ModelExperimentCandidateRequest:
    provider: str
    model: str


@dataclass(frozen=True)
class ModelExperimentCandidateResult:
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


@dataclass(frozen=True)
class ModelExperimentRun:
    id: str
    workspace_id: str
    question: str
    experiment_type: str
    status: str
    created_at: str
    completed_at: str | None
    shared_context_sources_count: int
    candidates: list[ModelExperimentCandidateResult]
    notes: list[str]
