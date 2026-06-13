# Task 212 — MCP setup UX and packaging direction cleanup

## Goal
Make MCP feel like a calm optional capability, not a scary engineering console.

MCP is powerful because servers may expose local files, repositories, memory stores, or future tools. The UI should therefore explain the flow in human terms and keep all actions explicit.

## UX changes

- The MCP section now starts with a short explanation and three simple metrics.
- The flow is shown as four calm steps:
  1. Choose a template
  2. Preview config
  3. Save disabled
  4. Approve read-only tools
- Setup, preview, workspace configs, and inventory are separated into disclosure sections.
- Advanced tool inventory is hidden until the user wants details.
- Saved configs stay visible when they exist.
- Empty states explain the next safe action.

## Safety rules kept

- Frontend does not run shell commands.
- Frontend does not start MCP servers.
- Backend does not execute MCP tools in this flow.
- Workspace configs are saved disabled by default.
- Read-only approval is the first supported approval path.
- Write/shell tools remain future sandbox work.

## Product direction

This keeps the app ready for a future desktop package:

- normal users see a simple local-first setup path;
- advanced users can still copy config JSON and manual commands;
- future agent plans can discover only explicitly approved tools;
- real MCP execution remains blocked until backend sandbox/allowlist execution exists.
