from dataclasses import dataclass


@dataclass(frozen=True)
class SelectedModelUsageCapability:
    id: str
    available: bool
    status: str
    reason: str


@dataclass(frozen=True)
class SelectedModelUsagePlan:
    workspace_id: str
    can_ask_with_selected_llm: bool
    can_index_with_selected_embedding: bool
    can_search_with_selected_embedding: bool
    can_use_selected_models_fully: bool
    selected_llm_provider: str | None
    selected_llm_model: str | None
    selected_embedding_provider: str | None
    selected_embedding_model: str | None
    active_llm_provider: str
    active_llm_model: str
    active_embedding_provider: str
    active_embedding_model: str
    index_status: str
    capabilities: list[SelectedModelUsageCapability]
    recommended_actions: list[str]
    notes: list[str]
