from pydantic import BaseModel, Field

from app.core.domain.model_experiment_rating import ModelExperimentCandidateRating


class RateModelExperimentCandidateRequest(BaseModel):
    provider: str
    model: str
    rating: int
    is_preferred: bool = False
    tags: list[str] = Field(default_factory=list)
    comment: str | None = None


class ModelExperimentCandidateRatingResponse(BaseModel):
    id: str
    experiment_id: str
    provider: str
    model: str
    rating: int
    is_preferred: bool
    tags: list[str]
    comment: str | None
    created_at: str


def to_model_experiment_candidate_rating_response(
    rating: ModelExperimentCandidateRating,
) -> ModelExperimentCandidateRatingResponse:
    return ModelExperimentCandidateRatingResponse(
        id=rating.id,
        experiment_id=rating.experiment_id,
        provider=rating.provider,
        model=rating.model,
        rating=rating.rating,
        is_preferred=rating.is_preferred,
        tags=rating.tags,
        comment=rating.comment,
        created_at=rating.created_at,
    )
