# Task 250 — Tauri backend health readiness gate

## Goal

Harden the real app-owned Tauri backend startup path so the desktop shell treats the backend as ready only after `GET /health` returns HTTP 200.

Task 248 introduced the first real app-owned backend process lifecycle. Task 250 tightens the readiness contract: an open localhost TCP port is not enough. The desktop shell must verify the application-level health endpoint before reporting successful startup.

## Added

- Backend endpoint:
  - `GET /runtime/app-owned-backend-health-readiness`
- Tauri read-only command:
  - `get_backend_health_readiness_contract`
- Tauri readiness implementation:
  - `backend_health_is_ready`
  - `wait_for_backend_health`
- Check script:
  - `scripts/check_tauri_backend_health_readiness.sh`
- Backend test:
  - `backend/tests/test_app_owned_backend_health_readiness.py`
- Settings UI section:
  - `App-owned backend health readiness`

## Safety contract

The desktop shell:

- does not treat an open TCP port as readiness;
- requires HTTP `GET /health` to return `200`;
- if health never becomes ready, stops only the child process started by this app session;
- does not kill unknown processes by port;
- does not expose arbitrary shell execution to React;
- does not start scan, index, rebuild, MCP, Agent, or model downloads during launch.

## Validation

```bash
scripts/check_tauri_backend_health_readiness.sh
scripts/check_tauri_app_owned_backend_startup.sh
```

```bash
cd backend
python -m pytest -q tests/test_app_owned_backend_health_readiness.py tests/test_app_owned_backend_startup_implementation.py tests/test_api_inventory.py
```

```bash
cd frontend
npm ci
npm run build
```

Local Rust/Tauri validation still needs to run on the developer machine:

```bash
cd frontend
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri dev
```

## Next

After the macOS health-gated startup smoke passes, mirror the same runtime smoke on Windows and then move toward packaged macOS app smoke / signed DMG work.
