# Task 245 — Frozen backend runtime selection

Task 245 fixes the Settings release-candidate audit 500 error and adds the next Phase 22 runtime gate.

## Fixed

- `/runtime/release-candidate-audit` now returns the correct validation command schema and no longer fails with a Pydantic validation error.
- Frontend production build chunk warning is reduced by Vite manual chunking instead of hiding the warning.

## Added

- `GET /runtime/frozen-backend-runtime-selection`
- `scripts/check_tauri_runtime_selection.sh`
- Tauri read-only runtime selection metadata command
- Settings UI section for frozen/staged/manual runtime candidates

## Contract

Runtime selection is read-only in this task. The desktop shell still does not start backend processes. Future startup may prefer the frozen PyInstaller runtime only after manifest and smoke checks pass. Staged source runtime remains a developer fallback. Unknown localhost processes must never be killed by port.
