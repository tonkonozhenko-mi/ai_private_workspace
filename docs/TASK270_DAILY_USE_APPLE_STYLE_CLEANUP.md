# Task 270 — Daily-use Apple-style cleanup

## Goal

Make the packaged MVP feel like an app that can be used daily, not a developer dashboard.

## User pain addressed

- The UI repeated scan/index/model state in too many places.
- Settings showed release/GitHub/runbook/debug information that does not belong in a normal app settings screen.
- The Models screen mixed normal model setup with packaging, agents, MCP, experiments, and copy-only command blocks.
- Adding a project required manually pasting a path instead of opening a native folder picker.
- Checking/building the app required many separate commands.
- Some cards/buttons had uneven spacing, wrapping, and visual overlap.

## Changes

### Navigation

The main workspace tabs were reduced to:

- Home
- Ask
- Models
- Settings

Reports, Capabilities, and Activity are no longer first-class tabs in the daily UI.

### Home / Overview

The Home screen now focuses on one daily-use flow:

1. Scan project
2. Build search context
3. Fix models if needed
4. Ask the workspace

Duplicate metric cards and repeated product status sections were removed or moved behind an Advanced disclosure.

### Create workspace

The Create workspace screen now has a visible **Choose folder** action.

In packaged macOS builds this calls a narrow Tauri command that opens the native folder picker and returns the selected local path.

The browser dev server still supports manual path paste.

### Models

The Models screen now shows:

- current answer model
- current search/context model
- direct runtime next action
- local model manager
- advanced model preference editor behind disclosure
- manual copy-only commands behind disclosure

Heavy product/packaging/agent/MCP/experiment panels are no longer rendered in the normal flow.

### Settings

Settings was rewritten as a user-facing screen with only:

- Appearance
- Models shortcut
- Project file rules
- Ask guidance

Release notes, GitHub handoff, release gate, desktop runbook, and developer diagnostics were removed from the normal Settings UI.

### One-command smoke

Added:

```bash
./scripts/run_desktop_mvp_smoke.sh
```

This wraps the major checks/build steps into one command for local verification.

### UI contract

Added:

```bash
./scripts/check_daily_use_ui_contracts.sh
```

It checks that the daily app UI remains simplified and does not regress into a developer dashboard.

## Safety

- Frontend still does not execute shell commands.
- Scan/index/ask still require explicit user clicks.
- Model downloads remain explicit and controlled.
- The macOS folder picker is a narrow Tauri command, not arbitrary command execution from React.
- Backend lifecycle rules are unchanged.

## Manual smoke

```bash
cd /Users/maks/Documents/ai_workspace
./scripts/run_desktop_mvp_smoke.sh
open "frontend/src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

Then verify:

1. Main tabs are Home / Ask / Models / Settings.
2. Add project has Choose folder.
3. Home does not duplicate scan/index/model status everywhere.
4. Models is usable without scrolling through packaging/agent/MCP panels.
5. Settings does not show release/GitHub/runbook sections.
6. Scan → Build context → Ask still works.
7. Restart keeps Ask history.
