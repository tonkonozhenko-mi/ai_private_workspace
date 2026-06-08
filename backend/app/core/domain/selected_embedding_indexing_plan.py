from dataclasses import dataclass


@dataclass(frozen=True)
class SelectedEmbeddingIndexingPlan:
    workspace_id: str
    selected_provider: str | None
    selected_model: str | None
    active_provider: str
    active_model: str
    index_status: str
    can_index_now: bool
    can_search_now: bool
    requires_backend_restart: bool
    requires_reindex: bool
    requires_new_vector_collection: bool
    plan_status: str
    recommended_actions: list[str]
    warnings: list[str]
    notes: list[str]
