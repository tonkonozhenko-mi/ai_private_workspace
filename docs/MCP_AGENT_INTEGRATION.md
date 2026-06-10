# MCP and Safe Agent Integration

AI Private Workspace treats MCP as a tool registry first, not as an automatic execution layer.

## Current behavior

- MCP templates are local configuration previews.
- Generated configs are disabled by default.
- The browser UI never starts MCP servers.
- The backend does not execute MCP tools yet.
- Agent workflows remain manual checklists with user-reviewed steps.

## Recommended flow

1. Choose an MCP template.
2. Generate a config preview.
3. Review the risk level and exposed tools.
4. Start/test the MCP server manually outside the browser.
5. Enable read-only tools first.
6. Use the tools as context for future safe agent planning.

## Safety model

- Read-only MCP tools are the first supported target.
- Write/delete/shell tools need backend approval gates before they can be integrated.
- Every risky step must be explicit, reviewable, and user-confirmed.
- Project claims still need retrieved sources or explicit assumptions.

## Future direction

The next stages can add workspace-scoped MCP configs, live connection checks, tool inventory discovery, and eventually approved backend execution for a small allowlist of safe tools.

## Workspace MCP configs and approval gates

Task 190 adds workspace-saved MCP configs and a first approval-gate model.

The flow is intentionally conservative:

1. Pick a catalog template.
2. Save it as a disabled workspace config.
3. Review the exposed tools.
4. Approve only the minimum read-only tool set.
5. Future agent workflows can see approved tool inventory.
6. Execution still remains manual-gated and is not implemented as an automatic tool runner.

Important safety rules:

- Saved MCP configs are disabled by default.
- Tool approval stores intent only.
- The browser does not start MCP servers.
- The backend does not execute MCP tools in this foundation step.
- Shell/write/delete tools should not be approved until sandbox execution exists.

New local API surfaces:

- `GET /mcp/workspaces/{workspace_id}/configs`
- `POST /mcp/workspaces/{workspace_id}/configs`
- `PATCH /mcp/workspaces/{workspace_id}/configs/{config_id}`
- `DELETE /mcp/workspaces/{workspace_id}/configs/{config_id}`
- `GET /mcp/workspaces/{workspace_id}/tool-inventory`
- `POST /mcp/workspaces/{workspace_id}/configs/{config_id}/approval-preview`

## Task 192 update: evidence and execution readiness

Agent workflows now include an execution readiness view that maps each workflow step to approved workspace MCP tools. This is still advisory and manual-only:

- a step can show whether its proposed tool is approved, denied, or missing;
- blockers explain what must happen before the step can be tracked as manually executable;
- evidence can be attached to a step after the user checks results outside the browser;
- evidence may include a short summary and source paths;
- the browser still never executes MCP tools, shell commands, file edits, git operations, scans, indexes, rebuilds, or restarts.

This prepares the product for a future backend sandbox/allowlist execution layer without weakening the local-first safety rules.
