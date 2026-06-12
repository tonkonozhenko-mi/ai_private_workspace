from dataclasses import dataclass


@dataclass(frozen=True)
class SelectedModelRuntimeStatus:
    model_type: str
    selected_provider: str | None
    selected_model: str | None
    active_provider: str
    active_model: str
    matches_active_runtime: bool
    requires_backend_restart: bool
    requires_reindex: bool
    status: str
    message: str


@dataclass(frozen=True)
class WorkspaceModelSelectionStatus:
    workspace_id: str
    llm_status: SelectedModelRuntimeStatus
    embedding_status: SelectedModelRuntimeStatus
    overall_status: str
    recommended_actions: list[str]
    notes: list[str]
