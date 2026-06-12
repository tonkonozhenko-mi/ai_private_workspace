from pydantic import BaseModel, Field

from app.core.domain.workspace_model_selection import (
    WorkspaceModelSelection,
    WorkspaceSelectedModel,
)


class UpdateWorkspaceModelSelectionRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    model_type: str = Field(..., min_length=1)
    selected_reason: str | None = None


class WorkspaceSelectedModelResponse(BaseModel):
    provider: str
    model: str
    model_type: str
    selected_at: str
    selected_reason: str | None


class WorkspaceModelSelectionResponse(BaseModel):
    workspace_id: str
    selected_llm: WorkspaceSelectedModelResponse | None
    selected_embedding: WorkspaceSelectedModelResponse | None
    notes: list[str]


def to_workspace_selected_model_response(
    model: WorkspaceSelectedModel | None,
) -> WorkspaceSelectedModelResponse | None:
    if model is None:
        return None
    return WorkspaceSelectedModelResponse(
        provider=model.provider,
        model=model.model,
        model_type=model.model_type,
        selected_at=model.selected_at,
        selected_reason=model.selected_reason,
    )


def to_workspace_model_selection_response(
    selection: WorkspaceModelSelection,
) -> WorkspaceModelSelectionResponse:
    return WorkspaceModelSelectionResponse(
        workspace_id=selection.workspace_id,
        selected_llm=to_workspace_selected_model_response(selection.selected_llm),
        selected_embedding=to_workspace_selected_model_response(
            selection.selected_embedding
        ),
        notes=selection.notes,
    )
