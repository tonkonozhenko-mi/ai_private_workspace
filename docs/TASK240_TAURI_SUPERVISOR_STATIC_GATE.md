# Task 240 — Tauri supervisor static gate

Task 240 starts the next practical Phase 22 step without stretching the roadmap into many tiny tasks.
It turns the Tauri supervisor bridge from a simple scaffold into a stricter read-only contract that can be checked before backend process startup is implemented.

## Added

- `GET /runtime/tauri-supervisor-static-gate`
- `scripts/check_tauri_supervisor_bridge.sh`
- `get_supervisor_preflight` Tauri command in `frontend/src-tauri/src/main.rs`
- Settings UI section: **Tauri supervisor static gate**
- Backend test: `backend/tests/test_tauri_supervisor_static_gate.py`

## Safety boundaries

The Tauri bridge remains read-only in this task:

- no backend process startup;
- no arbitrary shell/process execution;
- no scan/index/rebuild/MCP/Agent/model downloads on launch;
- no kill-by-port behavior;
- app data and logs stay outside the app bundle.

## Why this matters

Before implementing real double-click startup, we need a hard gate that proves the desktop shell exposes only safe status/log/preflight commands. This prevents the app from accidentally becoming a hidden command runner while packaging work continues.

## Next larger step

Move to frozen/staged backend runtime selection and deterministic startup design. Do not keep adding v0.1 polish unless smoke-check finds a blocker.
