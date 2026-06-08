from dataclasses import dataclass


@dataclass(frozen=True)
class ModelExperimentCandidateRating:
    id: str
    experiment_id: str
    provider: str
    model: str
    rating: int
    is_preferred: bool
    tags: list[str]
    comment: str | None
    created_at: str
