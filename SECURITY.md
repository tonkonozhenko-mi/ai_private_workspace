# Security Policy

AI Private Workspace is designed as a local-first application for private projects.

## Security boundaries

- The frontend must not execute shell commands.
- Backend execution paths must be explicit, allowlisted, and auditable.
- Model download execution is disabled by default and must be opt-in.
- MCP and Agent execution are planning/manual tracking only until sandboxed execution is implemented.
- Desktop startup must not trigger scan, index, rebuild, model download, MCP, or Agent workflows automatically.

## Reporting security issues

If this repository becomes public, use private GitHub security advisories or contact the maintainer directly. Do not disclose sensitive findings in public issues.

## Sensitive data

Do not include private repositories, credentials, `.env` files, runtime databases, or generated local context data in issues, PRs, screenshots, or release archives.
