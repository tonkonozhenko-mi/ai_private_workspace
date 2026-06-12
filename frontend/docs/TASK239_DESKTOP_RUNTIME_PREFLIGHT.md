# Task 239 — Desktop Runtime Preflight

Task 239 starts the practical Phase 22 / v0.2 desktop runtime path by adding a read-only packaging preflight before any real Tauri process supervision work.

## Added

- `GET /runtime/desktop-runtime-preflight`
- `scripts/check_desktop_runtime_preflight.sh`
- Settings UI section: **Desktop runtime preflight**
- Backend tests for the endpoint and script safety contract

## Why this matters

The project is moving from a v0.1 source release candidate into the v0.2 desktop runtime foundation. Before implementing app-owned backend startup inside Tauri, the repository needs a repeatable checkpoint that verifies the current packaging inputs are present:

- backend entrypoint;
- backend runtime manifest;
- frontend static build;
- macOS package foundation script;
- Tauri scaffold.

The new preflight is intentionally read-only. It can report missing inputs and show commands, but it must not start services or execute risky actions.

## Safety rules preserved

- Frontend does not execute shell commands.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.
- The preflight script does not start `uvicorn`, Ollama, MCP servers, or agent workflows.
- Runtime data and logs remain outside app bundles and source release archives.
- Unknown processes on localhost ports must never be killed automatically.

## Suggested validation

```bash
./scripts/audit_release_candidate.sh
```

```bash
scripts/check_desktop_runtime_preflight.sh
```

```bash
cd backend
python -m pytest -q tests/test_desktop_runtime_preflight.py tests/test_desktop_runtime_readiness.py tests/test_api_inventory.py
```

```bash
cd frontend
npm ci
npm run build
```

## Roadmap position

- v0.1 / Phase 21: effectively complete; only local smoke-check and publication steps remain.
- v0.2 / Phase 22: started; current focus is deterministic desktop runtime staging.
- v1.0: still roughly 15–25 large tasks away.
