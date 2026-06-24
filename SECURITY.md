# Security Policy

AI Private Workspace is designed as a local-first application. Security and privacy boundaries are part of the product contract.

## Supported version

The current supported source release candidate is `v0.1`.

## Safety boundaries

- Frontend never executes shell commands.
- Desktop launch does not automatically scan, index, rebuild, download models, start MCP servers, or run Agent workflows.
- Model download execution is disabled by default and must be enabled in a trusted local backend runtime.
- Agent/MCP execution is intentionally not available in v0.1.
- Runtime data and local databases must not be committed or included in source release archives.

## Reporting issues

Please report vulnerabilities through GitHub before publicly disclosing them, using either:

- **Private vulnerability reporting** — the repository's **Security › Report a vulnerability** tab (preferred; the report stays private), or
- a regular **GitHub issue** for non-sensitive reports.

Include:

- affected version or commit;
- platform;
- reproduction steps;
- expected and actual behavior;
- whether private project data, command execution, model downloads, or local runtime data are involved.

## Out of scope for v0.1

The v0.1 release candidate is not a signed installer-grade product. Final installer signing, hardened runtime, automatic updates, and sandboxed Agent/MCP execution are part of the future v1.0 track.
