# Security Policy

AI Private Workspace is designed as a local-first tool. The default posture is to avoid external uploads and prevent frontend shell execution.

## Supported version

This repository currently publishes a v0.1 source release candidate.

## Reporting issues

Please open a private security report or contact the repository owner before publishing sensitive findings.

## Security boundaries

- Frontend must not execute shell commands.
- Model downloads must remain backend-owned, opt-in, and allowlisted.
- MCP/Agent execution must remain disabled until sandboxing, approval, and audit logging exist.
- Runtime databases and local project data must not be committed.
