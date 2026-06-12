# Task 273 — Daily-use stability and visual hardening

This pass focuses on making the app feel usable instead of exposing raw development details.

## Included

- Hardened dark theme surfaces so cards, inputs, Ask, Models, Settings, and status panels do not leak light backgrounds.
- Reduced visual weight of Ask composer and normalized typography/spacing.
- Added safer backend behavior when a selected Ollama model fails to load or answer: Ask returns a diagnostic answer instead of an unhelpful generic failure.
- Added file create/edit prompt guidance: the assistant should propose path/content/patch and ask for approval, not claim it changed the computer directly.
- Added one-command/double-click launch helpers:
  - `./scripts/open_ai_private_workspace.sh`
  - `./scripts/build_and_open_ai_private_workspace.sh`
  - `Open AI Private Workspace.command`
- Added contract check: `./scripts/check_daily_use_stability_contracts.sh`.

## Manual check

1. Build/open with `./scripts/build_and_open_ai_private_workspace.sh` or double-click `Open AI Private Workspace.command`.
2. Switch to Dark theme.
3. Check Home, Ask, Models, Settings for light leaks and overflow.
4. Ask a normal source-backed question.
5. Switch to a model that is not available or too heavy.
6. Ask again. The UI should show a friendly model/runtime diagnostic, not a raw `Load failed` dead end.
7. Ask to create a file. The assistant should propose safe file content/patch and explain approval is required.

## Safety

The new launch helpers do not kill processes. They only open an existing `.app` or build and open the packaged app.
