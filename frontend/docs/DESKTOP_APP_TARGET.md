# Desktop app target

The current app is intentionally in a developer-safe packaging stage. Scripts are visible because they make local runtime behavior easy to debug before the product is wrapped as a real desktop application.

## What the final app should feel like

The final user experience should be:

```text
Download package -> double-click app -> local services start -> UI opens -> continue workspace
```

The user should not need to clone the repository, install frontend dependencies, run backend scripts, or read terminal logs for normal use.

## Why the current scripts still exist

The scripts are a bridge, not the final UX:

- they make backend/frontend startup explicit;
- they avoid hidden scans, model pulls, or MCP execution;
- they keep runtime data outside generated update archives;
- they make packaging failures easier to debug before a Tauri/Electron wrapper is added.

## In-app startup guidance rule

In-app startup guidance must not pretend to be the primary way to learn how to launch the app. If the user can see the UI, the app is already launched.

Therefore:

- external docs explain how to start the current build;
- the UI explains what to do after launch;
- future packaged builds should replace script instructions with app-level status and recovery actions.

## Packaging milestones

1. **Current:** repo + explicit scripts + optional macOS shortcut.
2. **Next:** desktop shell proof of concept with local backend supervisor.
3. **Then:** macOS `.app` package with bundled frontend and safe backend startup.
4. **Then:** Windows `.exe` / `.msi` equivalent.
5. **Later:** signed installers, auto-update strategy, and migration-safe update flow.

## Safety boundaries

Even in the packaged app:

- model downloads require explicit user approval;
- scan/index actions require explicit user click;
- MCP servers/tools are configured and approval-gated before execution;
- frontend never directly runs arbitrary shell commands;
- runtime data is protected from app updates.
