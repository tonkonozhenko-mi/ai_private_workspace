from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSwitchImpact:
    area: str
    impact: str
    requires_reindex: bool
    requires_backend_restart: bool
    risk: str
    explanation: str


@dataclass(frozen=True)
class ModelSwitchingPlan:
    workspace_id: str | None
    model_type: str
    current_provider: str
    current_model: str
    target_provider: str
    target_model: str
    requires_reindex: bool
    requires_new_vector_collection: bool
    can_switch_without_reindex: bool
    requires_backend_restart: bool
    recommended_actions: list[str]
    impacts: list[ModelSwitchImpact]
    notes: list[str]
