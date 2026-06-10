from pydantic import BaseModel, Field

from app.core.domain.mcp_server import (
    MCPServerCatalog,
    MCPServerConfigPreview,
    MCPServerConnectionCheck,
    MCPServerTemplate,
)


class MCPServerTemplateResponse(BaseModel):
    id: str
    name: str
    category: str
    description: str
    transport: str
    command: str
    args: list[str]
    env_vars: list[str]
    default_scope: str
    risk_level: str
    capabilities: list[str]
    example_tools: list[str]
    setup_notes: list[str]


class MCPServerCatalogResponse(BaseModel):
    summary: str
    templates: list[MCPServerTemplateResponse]
    safety_note: str
    recommended_flow: list[str]


class MCPConfigPreviewRequest(BaseModel):
    template_id: str
    workspace_id: str | None = None
    project_path: str | None = None
    env_overrides: dict[str, str] = Field(default_factory=dict)


class MCPServerConfigPreviewResponse(BaseModel):
    template_id: str
    name: str
    transport: str
    command: str
    args: list[str]
    env: dict[str, str]
    config_json: dict[str, object]
    risk_level: str
    scope: str
    allowed_by_default: bool
    guardrails: list[str]
    setup_steps: list[str]
    test_plan: list[str]
    generated_at: str


class MCPConnectionCheckRequest(BaseModel):
    template_id: str


class MCPServerConnectionCheckResponse(BaseModel):
    template_id: str
    status: str
    summary: str
    checks: list[str]
    warnings: list[str]
    copy_commands: list[str]
    safety_note: str


def to_mcp_template_response(template: MCPServerTemplate) -> MCPServerTemplateResponse:
    return MCPServerTemplateResponse(**template.__dict__)


def to_mcp_catalog_response(catalog: MCPServerCatalog) -> MCPServerCatalogResponse:
    return MCPServerCatalogResponse(
        summary=catalog.summary,
        templates=[to_mcp_template_response(template) for template in catalog.templates],
        safety_note=catalog.safety_note,
        recommended_flow=catalog.recommended_flow,
    )


def to_mcp_config_preview_response(preview: MCPServerConfigPreview) -> MCPServerConfigPreviewResponse:
    return MCPServerConfigPreviewResponse(**preview.__dict__)


def to_mcp_connection_check_response(check: MCPServerConnectionCheck) -> MCPServerConnectionCheckResponse:
    return MCPServerConnectionCheckResponse(**check.__dict__)
