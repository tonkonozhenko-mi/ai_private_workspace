from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating
from app.core.ports.model_experiment_rating_repository import (
    ModelExperimentRatingRepositoryPort,
)
from app.core.ports.model_experiment_repository import ModelExperimentRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)


@dataclass(frozen=True)
class RateModelExperimentCandidateInput:
    experiment_id: str
    provider: str
    model: str
    rating: int
    is_preferred: bool = False
    tags: list[str] = field(default_factory=list)
    comment: str | None = None


class ModelExperimentRatingValidationError(ValueError):
    pass


class ModelExperimentRatingNotFoundError(ValueError):
    pass


class RateModelExperimentCandidateUseCase:
    def __init__(
        self,
        model_experiment_repository: ModelExperimentRepositoryPort,
        rating_repository: ModelExperimentRatingRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.model_experiment_repository = model_experiment_repository
        self.rating_repository = rating_repository
        self.timeline_repository = timeline_repository

    def execute(
        self,
        request: RateModelExperimentCandidateInput,
    ) -> ModelExperimentCandidateRating:
        run = self.model_experiment_repository.get(request.experiment_id)
        if run is None:
            raise ModelExperimentRatingNotFoundError("Model experiment not found")

        provider = request.provider.strip().lower()
        model = request.model.strip()
        if not provider or not model:
            raise ModelExperimentRatingValidationError("Candidate provider and model are required")
        if not any(
            candidate.provider == provider and candidate.model == model
            for candidate in run.candidates
        ):
            raise ModelExperimentRatingNotFoundError("Model experiment candidate not found")
        if not 1 <= request.rating <= 5:
            raise ModelExperimentRatingValidationError("Rating must be between 1 and 5")

        comment = request.comment.strip() if request.comment is not None else None
        if comment == "":
            comment = None
        tags = list(dict.fromkeys(tag.strip() for tag in request.tags if tag.strip()))
        rating = self.rating_repository.save(
            ModelExperimentCandidateRating(
                id=str(uuid4()),
                experiment_id=run.id,
                provider=provider,
                model=model,
                rating=request.rating,
                is_preferred=request.is_preferred,
                tags=tags,
                comment=comment,
                created_at=datetime.now(UTC).isoformat(),
            )
        )

        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=run.workspace_id,
                    event_type="model_experiment_rated",
                    title="Model experiment rated",
                    summary=f"Rated {provider}/{model} with {request.rating}/5.",
                    metadata={
                        "experiment_id": run.id,
                        "provider": provider,
                        "model": model,
                        "rating": str(request.rating),
                        "is_preferred": str(request.is_preferred).lower(),
                    },
                )
            )
        return rating
