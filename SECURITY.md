# Security Policy

AI Private Workspace is designed as a local-first application. Security issues usually matter most around local files, model downloads, MCP tools, agents, and desktop process supervision.

## Supported version

The current supported line is the v0.1 source release candidate.

## Safety boundaries

- The frontend must not execute shell commands.
- Model downloads must be backend-side, opt-in, allowlisted, and explicitly approved.
- MCP servers and tools must not start automatically.
- Agent workflows must not execute tools without explicit future sandbox/allowlist controls.
- Desktop launch must not start scan, index, rebuild, MCP, agent, or model-download actions automatically.

## Reporting issues

Please open a private security report or contact the repository owner with:

- affected component;
- reproduction steps;
- expected and actual behavior;
- any logs with private paths or secrets removed.

Do not include private source code, credentials, tokens, API keys, or company data in public issues.
