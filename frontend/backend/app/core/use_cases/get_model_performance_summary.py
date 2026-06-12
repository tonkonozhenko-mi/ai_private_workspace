from collections import Counter
from dataclasses import dataclass, field

from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating
from app.core.domain.model_experiment_run import ModelExperimentCandidateResult
from app.core.domain.model_performance import (
    ModelPerformanceItem,
    ModelPerformanceSummary,
)
from app.core.ports.model_experiment_rating_repository import (
    ModelExperimentRatingRepositoryPort,
)
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort


PERFORMANCE_NOTES = [
    "Performance is aggregated from saved experiment results and manual ratings.",
    "Scores are deterministic signals, not a semantic quality evaluation.",
    "Only recent workspace experiment runs within the requested limit are included.",
]


@dataclass(frozen=True)
class GetModelPerformanceSummaryInput:
    workspace_id: str
    limit: int = 20


@dataclass
class _ModelAccumulator:
    provider: str
    model: str
    experiment_ids: set[str] = field(default_factory=set)
    completed_runs_count: int = 0
    failed_runs_count: int = 0
    latencies_ms: list[int] = field(default_factory=list)
    quality_warnings_counts: list[int] = field(default_factory=list)
    sources_counts: list[int] = field(default_factory=list)
    ratings: list[ModelExperimentCandidateRating] = field(default_factory=list)


class ModelPerformanceWorkspaceNotFoundError(ValueError):
    pass


class GetModelPerformanceSummaryUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        model_experiment_repository: ModelExperimentRepositoryPort,
        rating_repository: ModelExperimentRatingRepositoryPort,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.model_experiment_repository = model_experiment_repository
        self.rating_repository = rating_repository

    def execute(
        self,
        request: GetModelPerformanceSummaryInput,
    ) -> ModelPerformanceSummary:
        if self.workspace_repository.get(request.workspace_id) is None:
            raise ModelPerformanceWorkspaceNotFoundError("Workspace not found")

        runs = self.model_experiment_repository.list_by_workspace(
            request.workspace_id,
            max(0, request.limit),
        )
        accumulators: dict[tuple[str, str], _ModelAccumulator] = {}

        for run in runs:
            ratings = self.rating_repository.list_by_experiment(run.id)
            processed_candidates: set[tuple[str, str]] = set()
            for candidate in run.candidates:
                key = (candidate.provider, candidate.model)
                if key in processed_candidates:
                    continue
                processed_candidates.add(key)
                accumulator = accumulators.setdefault(
                    key,
                    _ModelAccumulator(
                        provider=candidate.provider,
                        model=candidate.model,
                    ),
                )
                self._add_candidate(accumulator, run.id, candidate)
                accumulator.ratings.extend(
                    rating
                    for rating in ratings
                    if rating.provider == candidate.provider
                    and rating.model == candidate.model
                )

        items = [self._to_item(accumulator) for accumulator in accumulators.values()]
        items.sort(
            key=lambda item: (
                -item.score,
                -(item.average_rating if item.average_rating is not None else -1),
                -item.preferred_votes,
                item.provider,
                item.model,
            )
        )
        return ModelPerformanceSummary(
            workspace_id=request.workspace_id,
            items=items,
            notes=list(PERFORMANCE_NOTES),
        )

    @staticmethod
    def _add_candidate(
        accumulator: _ModelAccumulator,
        experiment_id: str,
        candidate: ModelExperimentCandidateResult,
    ) -> None:
        accumulator.experiment_ids.add(experiment_id)
        if candidate.status == "completed":
            accumulator.completed_runs_count += 1
        else:
            accumulator.failed_runs_count += 1
        if candidate.latency_ms is not None:
            accumulator.latencies_ms.append(candidate.latency_ms)
        accumulator.quality_warnings_counts.append(candidate.quality_warnings_count)
        accumulator.sources_counts.append(candidate.sources_count)

    @classmethod
    def _to_item(cls, accumulator: _ModelAccumulator) -> ModelPerformanceItem:
        average_rating = cls._average(
            [rating.rating for rating in accumulator.ratings]
        )
        average_latency_ms = cls._average(accumulator.latencies_ms)
        average_quality_warnings_count = cls._average(
            accumulator.quality_warnings_counts
        )
        average_sources_count = cls._average(accumulator.sources_counts)
        preferred_votes = sum(rating.is_preferred for rating in accumulator.ratings)
        score, score_reasons = cls._score(
            completed_runs_count=accumulator.completed_runs_count,
            failed_runs_count=accumulator.failed_runs_count,
            average_rating=average_rating,
            preferred_votes=preferred_votes,
            average_quality_warnings_count=average_quality_warnings_count,
            average_sources_count=average_sources_count,
            average_latency_ms=average_latency_ms,
        )
        return ModelPerformanceItem(
            provider=accumulator.provider,
            model=accumulator.model,
            experiments_count=len(accumulator.experiment_ids),
            completed_runs_count=accumulator.completed_runs_count,
            failed_runs_count=accumulator.failed_runs_count,
            ratings_count=len(accumulator.ratings),
            average_rating=average_rating,
            preferred_votes=preferred_votes,
            average_latency_ms=average_latency_ms,
            average_quality_warnings_count=average_quality_warnings_count,
            average_sources_count=average_sources_count,
            common_tags=cls._common_tags(accumulator.ratings),
            score=score,
            score_reasons=score_reasons,
        )

    @staticmethod
    def _score(
        *,
        completed_runs_count: int,
        failed_runs_count: int,
        average_rating: float | None,
        preferred_votes: int,
        average_quality_warnings_count: float | None,
        average_sources_count: float | None,
        average_latency_ms: float | None,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []

        completed_points = completed_runs_count * 10
        if completed_points:
            score += completed_points
            reasons.append(f"+{completed_points}: {completed_runs_count} completed runs.")

        failed_penalty = failed_runs_count * 10
        if failed_penalty:
            score -= failed_penalty
            reasons.append(f"-{failed_penalty}: {failed_runs_count} failed or skipped runs.")

        if average_rating is not None and average_rating >= 4:
            score += 10
            reasons.append("+10: Average user rating is at least 4.")

        preferred_points = min(preferred_votes * 5, 25)
        if preferred_points:
            score += preferred_points
            reasons.append(f"+{preferred_points}: Preferred-vote signal.")

        if (
            average_quality_warnings_count is not None
            and average_quality_warnings_count > 0
        ):
            score -= 5
            reasons.append("-5: Average quality-warning count is above 0.")

        if average_sources_count is not None and average_sources_count > 0:
            score += 5
            reasons.append("+5: Average source count is above 0.")

        if average_latency_ms is not None and average_latency_ms < 3000:
            score += 5
            reasons.append("+5: Average latency is below 3000 ms.")

        return score, reasons

    @staticmethod
    def _average(values: list[int]) -> float | None:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _common_tags(
        ratings: list[ModelExperimentCandidateRating],
    ) -> list[str]:
        counts = Counter(tag for rating in ratings for tag in rating.tags)
        return [
            tag
            for tag, _ in sorted(
                counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ]
