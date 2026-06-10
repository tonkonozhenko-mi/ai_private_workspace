from fastapi import APIRouter, HTTPException, status

from app.api.schemas.mcp_schemas import (
    MCPConfigPreviewRequest,
    MCPConnectionCheckRequest,
    MCPServerCatalogResponse,
    MCPServerConfigPreviewResponse,
    MCPServerConnectionCheckResponse,
    to_mcp_catalog_response,
    to_mcp_config_preview_response,
    to_mcp_connection_check_response,
)
from app.core.domain.mcp_server import (
    build_mcp_config_preview,
    build_mcp_connection_check,
    find_mcp_template,
    list_mcp_server_catalog,
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
