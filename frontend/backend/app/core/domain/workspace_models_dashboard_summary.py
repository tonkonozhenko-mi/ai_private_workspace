from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceModelsDashboardSummary:
    workspace_id: str
    overall_status: str
    primary_next_action_id: str | None
    primary_next_action_title: str | None
    selected_llm: str | None
    selected_embedding: str | None
    active_llm: str
    active_embedding: str
    can_ask_with_selected_llm: bool
    can_search_with_selected_embedding: bool
    selected_embedding_matches_active_runtime: bool
    embedding_index_status: str
    embedding_plan_status: str
    top_recommended_model: str | None
    top_recommended_model_score: int | None
    performance_models_count: int
    warnings_count: int
    notes: list[str]
