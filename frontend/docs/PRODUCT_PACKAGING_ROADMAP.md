# Product packaging roadmap

AI Private Workspace is already close to a local MVP, but there are two different levels of packaging:

1. **Developer-safe local app** — current state. The user can run the backend/frontend locally with explicit scripts. This keeps every runtime action visible while the app is still changing quickly.
2. **Installer-grade desktop app** — target state. The user downloads a packaged macOS/Windows app, double-clicks it, and the app starts the local services behind a normal desktop shell.

## Current position

The project now has:

- local workspace data safety;
- backend/frontend startup scripts;
- macOS launcher foundation;
- optional macOS `.app` wrapper;
- post-launch readiness checks;
- guided local model setup;
- safe agent and MCP planning foundation.

This is enough for a release-candidate style developer build, but not yet enough for a non-technical user installer.

## True desktop app target

The expected final experience is:

1. Download the app package.
2. Double-click AI Private Workspace.
3. The desktop shell starts the local backend safely.
4. The UI opens automatically.
5. The app shows post-launch readiness.
6. The user chooses models, creates a workspace, scans, indexes, asks, and generates reports from the UI.

No repository clone, no manual `npm`, no manual `uvicorn`, and no terminal-first workflow should be required in the final packaged version.

## Model download manager

Model download support should be implemented before the final installer, but after first-launch UX is stable. The safe design is:

- show recommended LLM and embedding models;
- explain what each model is used for;
- show approximate size and hardware expectations when available;
- let the user choose a model;
- require explicit confirmation before any pull/download command;
- never auto-download from the frontend on page load;
- verify installed models after the user-approved action;
- keep custom model names available for advanced users.

Recommended next task cluster:

- Task 201: Ollama model availability and install plan API.
- Task 202: model download manager UI with copy/approval-only commands.
- Task 203: optional backend allowlisted execution for `ollama pull`, with explicit approval and logs.

## MCP server lifecycle

MCP should not be treated as a simple download button. MCP servers can expose powerful tools, so the product should keep this sequence:

1. Server registry and explanation.
2. Workspace-level MCP config.
3. Tool inventory and risk labels.
4. Approval gates for planned tool use.
5. Connection checks.
6. Only later: sandboxed/allowlisted execution.

Recommended next task cluster:

- Task 204: MCP install/config guide per server.
- Task 205: MCP connection test UX.
- Task 206: MCP approval policy and sandbox execution design.

## Packaging sequence

Recommended order from here:

1. Finish first-run UX and release-candidate cleanup.
2. Add model availability/download manager.
3. Add MCP install/config readiness.
4. Build a real macOS desktop package.
5. Build a Windows package.
6. Only after that, add real safe agent execution.

The app should stay local-first: no hidden network calls, no hidden model pulls, no automatic scans, and no frontend shell execution.
