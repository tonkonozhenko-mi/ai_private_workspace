from app.core.domain.model_experiment_comparison import (
    ModelExperimentCandidateComparison,
    ModelExperimentComparisonSummary,
)
from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating
from app.core.domain.model_experiment_run import ModelExperimentCandidateResult
from app.core.ports.model_experiment_rating_repository import (
    ModelExperimentRatingRepositoryPort,
)
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort

COMPARISON_NOTES = [
    "This comparison uses deterministic scoring only.",
    "Scores are not a semantic quality evaluation of candidate answers.",
    "A future AI-assisted evaluator can add deeper answer-quality analysis.",
]


class ModelExperimentComparisonNotFoundError(ValueError):
    pass


class GetModelExperimentComparisonUseCase:
    def __init__(
        self,
        repository: ModelExperimentRepositoryPort,
        rating_repository: ModelExperimentRatingRepositoryPort | None = None,
    ) -> None:
        self.repository = repository
        self.rating_repository = rating_repository

    def execute(self, experiment_id: str) -> ModelExperimentComparisonSummary:
        run = self.repository.get(experiment_id)
        if run is None:
            raise ModelExperimentComparisonNotFoundError("Model experiment not found")

        ratings = (
            self.rating_repository.list_by_experiment(run.id)
            if self.rating_repository is not None
            else []
        )
        comparisons = [
            self._compare(candidate, self._candidate_ratings(candidate, ratings))
            for candidate in run.candidates
        ]
        completed_count = sum(comparison.status == "completed" for comparison in comparisons)
        return ModelExperimentComparisonSummary(
            experiment_id=run.id,
            workspace_id=run.workspace_id,
            question=run.question,
            experiment_status=run.status,
            candidates_count=len(comparisons),
            completed_candidates_count=completed_count,
            failed_candidates_count=len(comparisons) - completed_count,
            recommended_candidate=self._recommended_candidate(comparisons),
            comparisons=comparisons,
            notes=list(COMPARISON_NOTES),
        )

    @staticmethod
    def _compare(
        candidate: ModelExperimentCandidateResult,
        ratings: list[ModelExperimentCandidateRating],
    ) -> ModelExperimentCandidateComparison:
        answer_length = len(candidate.answer or "")
        score = 0
        score_reasons: list[str] = []
        warnings: list[str] = []

        if candidate.status == "completed":
            score += 50
            score_reasons.append("+50: Candidate completed successfully.")
        else:
            score -= 50
            score_reasons.append("-50: Candidate failed or was skipped.")
            warnings.append(
                f"Candidate {candidate.status}: "
                f"{candidate.error or 'No error details were recorded.'}"
            )

        if candidate.sources_count > 0:
            score += 10
            score_reasons.append("+10: Candidate used retrieved sources.")
        else:
            warnings.append("Candidate has no retrieved sources.")

        if candidate.quality_warnings_count == 0:
            score += 10
            score_reasons.append("+10: Candidate has no quality warnings.")
        else:
            warning_penalty = min(candidate.quality_warnings_count * 5, 30)
            score -= warning_penalty
            score_reasons.append(
                f"-{warning_penalty}: Candidate has "
                f"{candidate.quality_warnings_count} quality warnings."
            )
            warnings.append(f"Candidate has {candidate.quality_warnings_count} quality warnings.")

        if answer_length > 100:
            score += 5
            score_reasons.append("+5: Candidate answer is longer than 100 characters.")
        if answer_length == 0:
            score -= 10
            score_reasons.append("-10: Candidate answer is empty.")
            warnings.append("Candidate answer is empty.")

        if candidate.latency_ms is not None and candidate.latency_ms < 3000:
            score += 5
            score_reasons.append("+5: Candidate latency is below 3000 ms.")

        return ModelExperimentCandidateComparison(
            provider=candidate.provider,
            model=candidate.model,
            status=candidate.status,
            answer_length=answer_length,
            latency_ms=candidate.latency_ms,
            sources_count=candidate.sources_count,
            quality_warnings_count=candidate.quality_warnings_count,
            score=score,
            score_reasons=score_reasons,
            warnings=warnings,
            user_ratings_count=len(ratings),
            average_user_rating=(
                sum(rating.rating for rating in ratings) / len(ratings) if ratings else None
            ),
            preferred_votes=sum(rating.is_preferred for rating in ratings),
        )

    @staticmethod
    def _candidate_ratings(
        candidate: ModelExperimentCandidateResult,
        ratings: list[ModelExperimentCandidateRating],
    ) -> list[ModelExperimentCandidateRating]:
        return [
            rating
            for rating in ratings
            if rating.provider == candidate.provider and rating.model == candidate.model
        ]

    @staticmethod
    def _recommended_candidate(
        comparisons: list[ModelExperimentCandidateComparison],
    ) -> str | None:
        completed = [comparison for comparison in comparisons if comparison.status == "completed"]
        if not completed:
            return None
        winner = max(completed, key=lambda comparison: comparison.score)
        return f"{winner.provider}/{winner.model}"
