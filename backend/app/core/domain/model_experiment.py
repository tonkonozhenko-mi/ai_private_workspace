from dataclasses import dataclass


@dataclass(frozen=True)
class ModelExperimentCandidate:
    provider: str
    model: str
    known_in_catalog: bool
    display_name: str | None
    model_type: str
    requires_reindex: bool
    requires_backend_restart: bool
    warnings: list[str]


@dataclass(frozen=True)
class ModelExperimentPlan:
    workspace_id: str
    question: str
    experiment_type: str
    candidates: list[ModelExperimentCandidate]
    shared_context_strategy: str
    requires_reindex: bool
    can_compare_without_reindex: bool
    recommended_actions: list[str]
    notes: list[str]
