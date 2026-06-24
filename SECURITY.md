# Security Policy

AI Private Workspace is designed as a local-first application. Security and privacy boundaries are part of the product contract.

## Supported version

The current supported release line is `v0.2.x`.

## Safety boundaries

AI Private Workspace is **read-only by default**: it reads your project, explains
it, and helps you understand it — it does not execute commands, modify files, run
external tools autonomously, or take actions on its own.

- The frontend never executes shell commands.
- Desktop launch does not automatically scan, index, rebuild, or download models.
- All on-device analysis (the project map, change review, deep analysis, security review) is read-only by construction: it never writes a file or runs a command.
- Model download execution is disabled by default and must be enabled in a trusted local backend runtime.
- The only write action is an explicit, consent-gated file draft in Ask — created only after you confirm the path and exact content.
- Runtime data and local databases must not be committed or included in source release archives.

## Out of scope

By design, the product does **not** do any of the following:

- upload your project or its contents to a remote/cloud service;
- make automatic code changes;
- execute shell commands on your behalf;
- run autonomous agents or external (MCP) tools without explicit, per-action consent.

## Reporting issues

Please report vulnerabilities through GitHub before publicly disclosing them, using either:

- **Private vulnerability reporting** — [open a private report](https://github.com/tonkonozhenko-mi/ai_private_workspace/security/advisories/new) (preferred; the report stays private), or
- a regular [GitHub issue](https://github.com/tonkonozhenko-mi/ai_private_workspace/issues/new) for non-sensitive reports.

Include:

- affected version or commit;
- platform;
- reproduction steps;
- expected and actual behavior;
- whether private project data, command execution, model downloads, or local runtime data are involved.

## Still on the road to 1.0

The app is not yet code-signed with a paid certificate, so first launch shows the
standard unsigned-app warning on macOS and Windows (see the README). Installer
signing and notarization, a hardened runtime, and broader QA are part of the v1.0
track. Releases are already signed for auto-update and ship SHA256 checksums and
an SPDX SBOM so you can verify what you download.
