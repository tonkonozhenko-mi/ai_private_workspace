from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPerformanceItem:
    provider: str
    model: str
    experiments_count: int
    completed_runs_count: int
    failed_runs_count: int
    ratings_count: int
    average_rating: float | None
    preferred_votes: int
    average_latency_ms: float | None
    average_quality_warnings_count: float | None
    average_sources_count: float | None
    common_tags: list[str]
    score: int
    score_reasons: list[str]


@dataclass(frozen=True)
class ModelPerformanceSummary:
    workspace_id: str | None
    items: list[ModelPerformanceItem]
    notes: list[str]
