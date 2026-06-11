# Security Policy

AI Private Workspace is designed for private, local-first project analysis. Treat all workspace data as sensitive.

## Supported status

This repository is currently a v0.1 source release candidate. It is suitable for local demos and development, not yet a signed commercial desktop release.

## Safety boundaries

- The frontend must not execute shell commands.
- Model downloads must remain backend-owned, explicit, opt-in, and allowlisted.
- MCP servers and Agent tools must not execute automatically.
- Runtime data must stay out of Git and release archives.
- Desktop launch must not scan, index, rebuild, download, or run tools automatically.

## Reporting issues

For private/internal use, report security issues through the repository owner or private issue channel. Do not include private project files, logs with secrets, or runtime databases in public issues.
