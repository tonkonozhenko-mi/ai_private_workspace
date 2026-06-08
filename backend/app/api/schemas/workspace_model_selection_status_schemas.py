from pydantic import BaseModel

from app.core.domain.workspace_model_selection_status import (
    SelectedModelRuntimeStatus,
    WorkspaceModelSelectionStatus,
)


class SelectedModelRuntimeStatusResponse(BaseModel):
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


class WorkspaceModelSelectionStatusResponse(BaseModel):
    workspace_id: str
    llm_status: SelectedModelRuntimeStatusResponse
    embedding_status: SelectedModelRuntimeStatusResponse
    overall_status: str
    recommended_actions: list[str]
    notes: list[str]


def to_selected_model_runtime_status_response(
    model_status: SelectedModelRuntimeStatus,
) -> SelectedModelRuntimeStatusResponse:
    return SelectedModelRuntimeStatusResponse(
        model_type=model_status.model_type,
        selected_provider=model_status.selected_provider,
        selected_model=model_status.selected_model,
        active_provider=model_status.active_provider,
        active_model=model_status.active_model,
        matches_active_runtime=model_status.matches_active_runtime,
        requires_backend_restart=model_status.requires_backend_restart,
        requires_reindex=model_status.requires_reindex,
        status=model_status.status,
        message=model_status.message,
    )


def to_workspace_model_selection_status_response(
    status: WorkspaceModelSelectionStatus,
) -> WorkspaceModelSelectionStatusResponse:
    return WorkspaceModelSelectionStatusResponse(
        workspace_id=status.workspace_id,
        llm_status=to_selected_model_runtime_status_response(status.llm_status),
        embedding_status=to_selected_model_runtime_status_response(
            status.embedding_status
        ),
        overall_status=status.overall_status,
        recommended_actions=status.recommended_actions,
        notes=status.notes,
    )
