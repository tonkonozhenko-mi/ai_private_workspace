from pydantic import BaseModel

from app.core.domain.model_performance import (
    ModelPerformanceItem,
    ModelPerformanceSummary,
)


class ModelPerformanceItemResponse(BaseModel):
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


class ModelPerformanceSummaryResponse(BaseModel):
    workspace_id: str | None
    items: list[ModelPerformanceItemResponse]
    notes: list[str]


def to_model_performance_item_response(
    item: ModelPerformanceItem,
) -> ModelPerformanceItemResponse:
    return ModelPerformanceItemResponse(
        provider=item.provider,
        model=item.model,
        experiments_count=item.experiments_count,
        completed_runs_count=item.completed_runs_count,
        failed_runs_count=item.failed_runs_count,
        ratings_count=item.ratings_count,
        average_rating=item.average_rating,
        preferred_votes=item.preferred_votes,
        average_latency_ms=item.average_latency_ms,
        average_quality_warnings_count=item.average_quality_warnings_count,
        average_sources_count=item.average_sources_count,
        common_tags=item.common_tags,
        score=item.score,
        score_reasons=item.score_reasons,
    )


def to_model_performance_summary_response(
    summary: ModelPerformanceSummary,
) -> ModelPerformanceSummaryResponse:
    return ModelPerformanceSummaryResponse(
        workspace_id=summary.workspace_id,
        items=[
            to_model_performance_item_response(item)
            for item in summary.items
        ],
        notes=summary.notes,
    )
