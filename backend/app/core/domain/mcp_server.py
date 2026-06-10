from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class MCPServerTemplate:
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


@dataclass(frozen=True)
class MCPServerCatalog:
    summary: str
    templates: list[MCPServerTemplate]
    safety_note: str
    recommended_flow: list[str]


@dataclass(frozen=True)
class MCPServerConfigPreview:
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


@dataclass(frozen=True)
class MCPServerConnectionCheck:
    template_id: str
    status: str
    summary: str
    checks: list[str]
    warnings: list[str]
    copy_commands: list[str]
    safety_note: str


MCP_TEMPLATES = [
    MCPServerTemplate(
        id="filesystem-readonly",
        name="Filesystem read-only",
        category="local_files",
        description="Expose selected project folders for read-only inspection through an MCP filesystem server.",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "${PROJECT_PATH}"],
        env_vars=["PROJECT_PATH"],
        default_scope="workspace",
        risk_level="read_only",
        capabilities=["list_files", "read_files", "search_files"],
        example_tools=["read_file", "list_directory", "search_files"],
        setup_notes=[
            "Point PROJECT_PATH to the workspace project path.",
            "Keep this read-only until explicit write tool support is designed.",
        ],
    ),
    MCPServerTemplate(
        id="git-readonly",
        name="Git read-only",
        category="repository",
        description="Inspect local git status, branches, recent commits, and diffs without pushing or changing files.",
        transport="stdio",
        command="uvx",
        args=["mcp-server-git", "--repository", "${PROJECT_PATH}"],
        env_vars=["PROJECT_PATH"],
        default_scope="workspace",
        risk_level="read_only",
        capabilities=["git_status", "git_log", "git_diff"],
        example_tools=["git_status", "git_log", "git_diff"],
        setup_notes=[
            "Use only against a local repository path.",
            "Write/push operations should remain disabled for now.",
        ],
    ),
    MCPServerTemplate(
        id="qdrant-readonly",
        name="Qdrant read-only",
        category="vector_store",
        description="Inspect local Qdrant collections and search context metadata for troubleshooting RAG quality.",
        transport="stdio",
        command="uvx",
        args=["mcp-server-qdrant", "--url", "${QDRANT_URL}"],
        env_vars=["QDRANT_URL"],
        default_scope="runtime",
        risk_level="read_only",
        capabilities=["list_collections", "inspect_collection", "search_points"],
        example_tools=["list_collections", "search_points"],
        setup_notes=[
            "Use the local Qdrant URL from backend environment.",
            "Keep delete/update tools disabled.",
        ],
    ),
    MCPServerTemplate(
        id="shell-proposed-commands",
        name="Shell proposed commands",
        category="execution",
        description="Prepare command suggestions for manual user approval. This app does not auto-run shell tools.",
        transport="manual",
        command="copy-only",
        args=[],
        env_vars=[],
        default_scope="manual_approval",
        risk_level="dangerous_requires_approval",
        capabilities=["propose_command", "explain_risk", "prepare_verification"],
        example_tools=["propose_command"],
        setup_notes=[
            "Use as a planning placeholder only.",
            "Execution must stay behind backend policy and user approval gates.",
        ],
    ),
]


def list_mcp_server_catalog() -> MCPServerCatalog:
    return MCPServerCatalog(
        summary=(
            "MCP support is modeled as a safe tool registry first. Servers can be planned, "
            "configured, and reviewed before any execution integration is enabled."
        ),
        templates=MCP_TEMPLATES,
        safety_note=(
            "MCP servers can expose powerful local tools. This workspace treats them as disabled "
            "until explicitly configured and approved per workspace."
        ),
        recommended_flow=[
            "Choose a template",
            "Generate a local config preview",
            "Review risk level and exposed tools",
            "Test connection manually",
            "Enable only read-only tools first",
            "Use tools in agent planning only until execution gates are implemented",
        ],
    )


def find_mcp_template(template_id: str) -> MCPServerTemplate | None:
    for template in MCP_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def build_mcp_config_preview(
    template: MCPServerTemplate,
    workspace_id: str | None,
    project_path: str | None,
    env_overrides: dict[str, str] | None = None,
) -> MCPServerConfigPreview:
    env = {key: "" for key in template.env_vars}
    if project_path and "PROJECT_PATH" in env:
        env["PROJECT_PATH"] = project_path
    if env_overrides:
        env.update({key: value for key, value in env_overrides.items() if key in env})

    config_json = {
        "mcpServers": {
            template.id: {
                "command": template.command,
                "args": template.args,
                "env": env,
                "disabled": True,
                "scope": template.default_scope,
                "riskLevel": template.risk_level,
            }
        }
    }
    if workspace_id:
        config_json["workspaceId"] = workspace_id

    return MCPServerConfigPreview(
        template_id=template.id,
        name=template.name,
        transport=template.transport,
        command=template.command,
        args=template.args,
        env=env,
        config_json=config_json,
        risk_level=template.risk_level,
        scope=template.default_scope,
        allowed_by_default=False,
        guardrails=[
            "Generated MCP configs are disabled by default.",
            "Read-only servers should be enabled before write-capable tools.",
            "The frontend never starts MCP servers or executes tools.",
            "Agent workflows may reference enabled tools only after user review.",
        ],
        setup_steps=[
            "Copy the generated config into your local MCP client configuration.",
            "Replace empty env values with local paths or localhost URLs.",
            "Start/test the server outside the browser UI.",
            "Return to this workspace and mark the tool set as reviewed before using it in an agent plan.",
        ],
        test_plan=[
            "Verify the MCP server process starts locally.",
            "List exposed tools and confirm there are no write/delete tools enabled accidentally.",
            "Run one read-only tool against a small known file/resource.",
            "Stop the server if the exposed tool list is broader than expected.",
        ],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def build_mcp_connection_check(template: MCPServerTemplate) -> MCPServerConnectionCheck:
    commands = []
    if template.transport == "stdio" and template.command != "copy-only":
        commands.append(" ".join([template.command, *template.args]))
    return MCPServerConnectionCheck(
        template_id=template.id,
        status="manual_check_required",
        summary="Connection testing is intentionally manual in this foundation step.",
        checks=[
            "Confirm the server command exists on this machine.",
            "Confirm required environment variables are set.",
            "Start the MCP server in a terminal and inspect the exposed tools.",
            "Keep the server disabled in this workspace until the tool list is reviewed.",
        ],
        warnings=[
            "The backend does not execute MCP tools yet.",
            "Do not enable write/delete/shell tools until backend approval gates are implemented.",
        ],
        copy_commands=commands,
        safety_note="This is a copy-only connection plan. No MCP process is started by the browser or backend.",
    )
