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


def to_mcp_config_preview_response(
    preview: MCPServerConfigPreview,
) -> MCPServerConfigPreviewResponse:
    return MCPServerConfigPreviewResponse(**preview.__dict__)


def to_mcp_connection_check_response(
    check: MCPServerConnectionCheck,
) -> MCPServerConnectionCheckResponse:
    return MCPServerConnectionCheckResponse(**check.__dict__)


from app.core.domain.mcp_server import (
    MCPApprovalPreview,
    MCPToolInventory,
    WorkspaceMCPServerConfig,
)


class CreateWorkspaceMCPConfigRequest(BaseModel):
    template_id: str
    project_path: str | None = None
    env_overrides: dict[str, str] = Field(default_factory=dict)


class UpdateWorkspaceMCPConfigRequest(BaseModel):
    enabled: bool | None = None
    reviewed: bool | None = None
    approved_tools: list[str] | None = None
    denied_tools: list[str] | None = None


class MCPApprovalPreviewRequest(BaseModel):
    approved_tools: list[str] = Field(default_factory=list)


class WorkspaceMCPServerConfigResponse(BaseModel):
    id: str
    workspace_id: str
    template_id: str
    name: str
    category: str
    transport: str
    command: str
    args: list[str]
    env: dict[str, str]
    config_json: dict[str, object]
    risk_level: str
    scope: str
    enabled: bool
    reviewed: bool
    available_tools: list[str]
    approved_tools: list[str]
    denied_tools: list[str]
    guardrails: list[str]
    status: str
    available_tools_count: int
    approved_tools_count: int
    created_at: str
    updated_at: str


class WorkspaceMCPConfigListResponse(BaseModel):
    workspace_id: str
    items: list[WorkspaceMCPServerConfigResponse]
    safety_note: str


class MCPToolInventoryResponse(BaseModel):
    workspace_id: str
    configs_count: int
    enabled_configs_count: int
    approved_tools_count: int
    read_only_tools_count: int
    write_or_dangerous_tools_count: int
    tools: list[dict[str, str]]
    safety_note: str
    agent_readiness: str


class MCPApprovalPreviewResponse(BaseModel):
    workspace_id: str
    config_id: str
    status: str
    approved_tools: list[str]
    denied_tools: list[str]
    warnings: list[str]
    guardrails: list[str]
    safety_note: str


def to_workspace_mcp_config_response(
    config: WorkspaceMCPServerConfig,
) -> WorkspaceMCPServerConfigResponse:
    return WorkspaceMCPServerConfigResponse(
        id=config.id,
        workspace_id=config.workspace_id,
        template_id=config.template_id,
        name=config.name,
        category=config.category,
        transport=config.transport,
        command=config.command,
        args=config.args,
        env=config.env,
        config_json=config.config_json,
        risk_level=config.risk_level,
        scope=config.scope,
        enabled=config.enabled,
        reviewed=config.reviewed,
        available_tools=config.available_tools,
        approved_tools=config.approved_tools,
        denied_tools=config.denied_tools,
        guardrails=config.guardrails,
        status=config.status,
        available_tools_count=config.available_tools_count,
        approved_tools_count=config.approved_tools_count,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def to_mcp_tool_inventory_response(inventory: MCPToolInventory) -> MCPToolInventoryResponse:
    return MCPToolInventoryResponse(**inventory.__dict__)


def to_mcp_approval_preview_response(preview: MCPApprovalPreview) -> MCPApprovalPreviewResponse:
    return MCPApprovalPreviewResponse(**preview.__dict__)
