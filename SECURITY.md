# Security Policy

AI Private Workspace is designed for local-first project analysis. The default posture is conservative: no automatic shell execution, no automatic model downloads, no automatic indexing, and no automatic MCP/tool execution.

## Safety boundaries

- Frontend is UI-only and must not run shell commands.
- Backend execution features must be explicit, allowlisted, and disabled by default where possible.
- Model download execution is opt-in and restricted to catalog models.
- MCP/Agent execution remains planning/manual tracking until sandbox and allowlist controls are implemented.
- Runtime data and local databases must never be committed.

## Reporting issues

For now, open a private issue or discuss directly with the repository owner before sharing sensitive details publicly.
