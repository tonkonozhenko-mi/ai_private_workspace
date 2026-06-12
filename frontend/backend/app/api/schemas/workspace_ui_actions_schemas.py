from pydantic import BaseModel

from app.core.domain.workspace_ui_actions import (
    WorkspaceUIAction,
    WorkspaceUIActionCatalog,
)


class WorkspaceUIActionResponse(BaseModel):
    id: str
    title: str
    description: str
    method: str
    endpoint: str
    category: str
    status: str
    is_primary: bool
    mutates_data: bool
    reason: str


class WorkspaceUIActionCatalogResponse(BaseModel):
    workspace_id: str
    primary_action_id: str | None
    actions: list[WorkspaceUIActionResponse]
    notes: list[str]


def to_workspace_ui_action_response(
    action: WorkspaceUIAction,
) -> WorkspaceUIActionResponse:
    return WorkspaceUIActionResponse(
        id=action.id,
        title=action.title,
        description=action.description,
        method=action.method,
        endpoint=action.endpoint,
        category=action.category,
        status=action.status,
        is_primary=action.is_primary,
        mutates_data=action.mutates_data,
        reason=action.reason,
    )


def to_workspace_ui_action_catalog_response(
    catalog: WorkspaceUIActionCatalog,
) -> WorkspaceUIActionCatalogResponse:
    return WorkspaceUIActionCatalogResponse(
        workspace_id=catalog.workspace_id,
        primary_action_id=catalog.primary_action_id,
        actions=[
            to_workspace_ui_action_response(action)
            for action in catalog.actions
        ],
        notes=catalog.notes,
    )
