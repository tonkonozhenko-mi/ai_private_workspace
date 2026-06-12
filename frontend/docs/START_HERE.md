# AI Private Workspace — start here

This file is the outside-the-app entry point. The app UI can explain what to do after it is open, but it cannot be the only place that explains how to start it.


## v0.1 handoff docs

For GitHub/demo review, read:

- `README.md` — repository landing page.
- `docs/V01_DEMO_HANDOFF.md` — demo scenario.
- `docs/V01_RELEASE_NOTES.md` — release notes and limitations.
- `docs/GITHUB_REPOSITORY_GUIDE.md` — repository cleanliness guide.
- `docs/RELEASE_CANDIDATE_AUDIT.md` — release audit policy.

## Current developer-safe startup

Until a real `.app` / `.exe` package is built, use one of these options from the project root.

### macOS one-command launcher

```bash
chmod +x scripts/launch_macos.command scripts/create_macos_shortcut.sh
./scripts/launch_macos.command
```

The launcher asks for confirmation, starts the local backend/frontend, and opens the local UI.
It does not pull models, scan projects, build indexes, run MCP tools, or execute agent workflows.

### Optional macOS app shortcut

```bash
./scripts/create_macos_shortcut.sh
open ~/Applications
```

Then drag **AI Private Workspace.app** to the Dock.
This shortcut is still a wrapper around the local launcher, not a final packaged installer.

## Final product target

The target desktop experience is:

1. Download installer/package.
2. Double-click the app.
3. App starts its local backend supervisor.
4. Browser-like UI opens inside the desktop shell.
5. User creates/opens a workspace.
6. User explicitly chooses models, scans, indexes, and runs tasks.

No repo clone, no manual scripts, and no hidden background model/tool execution should be required in the final packaged app.

## First screen after launch

After the UI is open, use the app checklist for:

- workspace setup;
- model selection;
- local search context;
- safe scan/index actions;
- reports and agent planning.

The in-app checklist is a post-launch guide. This file is the pre-launch guide.
