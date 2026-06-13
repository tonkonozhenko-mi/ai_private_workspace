# Task 242 — Desktop stack and runtime contract

## Result

Phase 22 now has an explicit stack decision and runtime staging contract instead of an implicit Tauri-only assumption.

## Accepted v0.2 direction

AI Private Workspace will continue with an open-source/free, cross-platform desktop stack:

- **Tauri + React** as the current lightweight desktop shell candidate for macOS and Windows.
- **React + TypeScript + Vite** as the shared UI.
- **FastAPI** as the local backend API.
- **SQLite + Qdrant + Ollama** for local-first persistence, retrieval, and model runtime.
- **PyInstaller-first** backend freeze spike, with Nuitka or packaged Python runtime kept as fallback options.

This is accepted for v0.2 implementation work, but it remains replaceable before v1.0 if macOS signing, Windows packaging, runtime freeze, or maintenance cost becomes worse than expected.

## Why this stack

Tauri is currently the best balance for this product because it allows one existing React UI to run on macOS and Windows with a small native supervisor layer. It is usually lighter than Electron and avoids maintaining separate SwiftUI and WinUI applications.

Electron remains a fallback, not the default, because it is mature but heavier. Separate native applications are rejected for now because they would create two UI codebases and duplicate QA.

## Runtime staging contract

Before the desktop shell is allowed to start the backend automatically, the backend runtime must be staged deterministically.

The staging contract is:

1. Desktop shell may start only the staged app-owned backend runtime, never arbitrary user commands.
2. Runtime staging must not include `backend/.ai-workbench`, databases, caches, `node_modules`, or unrelated build artifacts.
3. App data and logs must be created under OS user data locations, not inside the app bundle.
4. UI opens only after `/health` is ready or shows a local-log error screen.
5. Port handling must never kill unknown processes. The app may stop only a PID it started.

## Safety rules preserved

- Frontend still cannot execute shell commands.
- Desktop launch must not start scan, index, rebuild, MCP, Agent, or model downloads.
- Model downloads stay backend-side, opt-in, allowlisted, and explicitly approved.
- MCP servers/tools are not started automatically.
- Agent workflows remain approval-gated and do not execute tools automatically.

## Validation

```bash
./scripts/audit_release_candidate.sh
scripts/prepare_macos_backend_runtime.sh
scripts/check_desktop_runtime_preflight.sh
scripts/check_desktop_stack_contract.sh
```

Backend targeted test:

```bash
cd backend
python -m pytest -q tests/test_desktop_stack_runtime_contract.py tests/test_desktop_technology_decision.py tests/test_tauri_supervisor_static_gate.py tests/test_desktop_runtime_preflight.py tests/test_api_inventory.py
```

Frontend build:

```bash
cd frontend
npm ci
npm run build
```
