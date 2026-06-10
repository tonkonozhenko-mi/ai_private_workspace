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
