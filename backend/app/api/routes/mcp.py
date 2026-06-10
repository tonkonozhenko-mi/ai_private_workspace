from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import mcp_repository, workspace_repository
from app.api.schemas.mcp_schemas import (
    CreateWorkspaceMCPConfigRequest,
    MCPApprovalPreviewRequest,
    MCPApprovalPreviewResponse,
    MCPConfigPreviewRequest,
    MCPConnectionCheckRequest,
    MCPServerCatalogResponse,
    MCPToolInventoryResponse,
    MCPServerConfigPreviewResponse,
    MCPServerConnectionCheckResponse,
    UpdateWorkspaceMCPConfigRequest,
    WorkspaceMCPConfigListResponse,
    WorkspaceMCPServerConfigResponse,
    to_mcp_approval_preview_response,
    to_mcp_catalog_response,
    to_mcp_config_preview_response,
    to_mcp_connection_check_response,
    to_mcp_tool_inventory_response,
    to_workspace_mcp_config_response,
)
from app.core.domain.mcp_server import (
    build_mcp_approval_preview,
    build_mcp_config_preview,
    build_mcp_connection_check,
    build_mcp_tool_inventory,
    create_workspace_mcp_config_from_preview,
    find_mcp_template,
    list_mcp_server_catalog,
    update_workspace_mcp_config,
)


router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/catalog", response_model=MCPServerCatalogResponse)
def get_mcp_catalog() -> MCPServerCatalogResponse:
    return to_mcp_catalog_response(list_mcp_server_catalog())


@router.post("/config-preview", response_model=MCPServerConfigPreviewResponse)
def create_mcp_config_preview(request: MCPConfigPreviewRequest) -> MCPServerConfigPreviewResponse:
    template = find_mcp_template(request.template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server template not found: {request.template_id}",
        )
    preview = build_mcp_config_preview(
        template=template,
        workspace_id=request.workspace_id,
        project_path=request.project_path,
        env_overrides=request.env_overrides,
    )
    return to_mcp_config_preview_response(preview)


@router.post("/connection-check", response_model=MCPServerConnectionCheckResponse)
def create_mcp_connection_check(request: MCPConnectionCheckRequest) -> MCPServerConnectionCheckResponse:
    template = find_mcp_template(request.template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server template not found: {request.template_id}",
        )
    return to_mcp_connection_check_response(build_mcp_connection_check(template))


@router.get("/workspaces/{workspace_id}/configs", response_model=WorkspaceMCPConfigListResponse)
def list_workspace_mcp_configs(workspace_id: str) -> WorkspaceMCPConfigListResponse:
    _require_workspace(workspace_id)
    configs = mcp_repository.list_configs(workspace_id)
    return WorkspaceMCPConfigListResponse(
        workspace_id=workspace_id,
        items=[to_workspace_mcp_config_response(config) for config in configs],
        safety_note="Workspace MCP configs are disabled or tool-limited until reviewed. Tool execution is not automatic.",
    )


@router.post("/workspaces/{workspace_id}/configs", response_model=WorkspaceMCPServerConfigResponse)
def create_workspace_mcp_config(
    workspace_id: str,
    request: CreateWorkspaceMCPConfigRequest,
) -> WorkspaceMCPServerConfigResponse:
    _require_workspace(workspace_id)
    template = find_mcp_template(request.template_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server template not found: {request.template_id}")
    workspace = workspace_repository.get(workspace_id)
    preview = build_mcp_config_preview(
        template=template,
        workspace_id=workspace_id,
        project_path=request.project_path or (workspace.project_path if workspace else None),
        env_overrides=request.env_overrides,
    )
    config = create_workspace_mcp_config_from_preview(
        workspace_id=workspace_id,
        template=template,
        preview=preview,
    )
    return to_workspace_mcp_config_response(mcp_repository.save_config(config))


@router.patch("/workspaces/{workspace_id}/configs/{config_id}", response_model=WorkspaceMCPServerConfigResponse)
def update_workspace_mcp_config_route(
    workspace_id: str,
    config_id: str,
    request: UpdateWorkspaceMCPConfigRequest,
) -> WorkspaceMCPServerConfigResponse:
    config = _require_config(workspace_id, config_id)
    updated = update_workspace_mcp_config(
        config,
        enabled=request.enabled,
        reviewed=request.reviewed,
        approved_tools=request.approved_tools,
        denied_tools=request.denied_tools,
    )
    return to_workspace_mcp_config_response(mcp_repository.save_config(updated))


@router.delete("/workspaces/{workspace_id}/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_mcp_config(workspace_id: str, config_id: str) -> None:
    _require_workspace(workspace_id)
    if not mcp_repository.delete_config(workspace_id, config_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace MCP config not found")


@router.get("/workspaces/{workspace_id}/tool-inventory", response_model=MCPToolInventoryResponse)
def get_workspace_mcp_tool_inventory(workspace_id: str) -> MCPToolInventoryResponse:
    _require_workspace(workspace_id)
    inventory = build_mcp_tool_inventory(workspace_id, mcp_repository.list_configs(workspace_id))
    return to_mcp_tool_inventory_response(inventory)


@router.post("/workspaces/{workspace_id}/configs/{config_id}/approval-preview", response_model=MCPApprovalPreviewResponse)
def preview_workspace_mcp_approval(
    workspace_id: str,
    config_id: str,
    request: MCPApprovalPreviewRequest,
) -> MCPApprovalPreviewResponse:
    config = _require_config(workspace_id, config_id)
    preview = build_mcp_approval_preview(
        workspace_id=workspace_id,
        config=config,
        approved_tools=request.approved_tools,
    )
    return to_mcp_approval_preview_response(preview)


def _require_workspace(workspace_id: str) -> None:
    if workspace_repository.get(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")


def _require_config(workspace_id: str, config_id: str):
    _require_workspace(workspace_id)
    config = mcp_repository.get_config(workspace_id, config_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace MCP config not found")
    return config
