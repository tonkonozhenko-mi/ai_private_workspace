# Task 249 — macOS frozen runtime and Tauri smoke runbook

## Goal

Create a short, explicit local runbook for proving the macOS desktop path before moving to Windows parity and signed installers.

This is not a new feature. It is a release-engineering gate for the desktop runtime:

```text
backend source
  -> PyInstaller frozen backend runtime
  -> frozen backend smoke
  -> Tauri app-owned backend startup smoke
  -> future signed macOS app / DMG
```

## Safety contract

- React/frontend does not execute shell commands.
- Tauri may start only the executable referenced by the app-owned frozen backend manifest.
- Shutdown is PID-owned; never kill unknown processes by port.
- If port `8000` is already occupied, startup must fail with a clear message.
- No scan, index, rebuild, MCP, Agent, or model download starts on launch.
- Runtime data and logs stay outside the app bundle.

## Local macOS smoke sequence

Run from the project root.

### 1. Verify source gates

```bash
./scripts/audit_release_candidate.sh
scripts/check_macos_tauri_smoke_runbook.sh
scripts/check_tauri_app_owned_backend_startup.sh
```

### 2. Build the frozen backend runtime

```bash
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
```

Expected output:

```text
build/desktop/frozen-backend-runtime/
  AI_PRIVATE_WORKSPACE_FROZEN_RUNTIME_MANIFEST.json
  <backend executable>
```

### 3. Smoke the frozen backend outside Tauri

```bash
scripts/smoke_frozen_backend_runtime.sh
```

Pass criteria:

- the script starts only the generated backend executable;
- `/health` responds on `127.0.0.1:8000`;
- the script stops only the PID it created;
- no kill-by-port behavior is used.

### 4. Compile-check the Tauri shell

```bash
cd frontend
cargo check --manifest-path src-tauri/Cargo.toml
```

If Rust/Tauri dependencies are missing, install the local toolchain first. This is a developer-machine check, not a backend feature.

### 5. Run the Tauri local smoke

```bash
cd frontend
npm run tauri dev
```

Manual checks:

- the app starts only the app-owned frozen backend runtime;
- the UI opens only after backend health is ready;
- status/log path commands show app-owned paths;
- closing/stopping the app stops only the spawned backend PID;
- launch does not trigger scan, index, rebuild, MCP, Agent, or model downloads.

## If it fails

Fix the first failure only, then rerun the smoke sequence from the relevant step.

Common failure areas:

- PyInstaller hidden imports or missing resources;
- wrong manifest path inside the app bundle;
- port `8000` already occupied;
- backend executable cannot find packaged dependencies;
- Tauri Rust compile errors.

## Next after this passes

1. Mirror the same frozen runtime smoke contract on Windows.
2. Move macOS packaging from developer smoke to `.app`/DMG packaging.
3. Add signing/notarization plan.
4. Add update-safe runtime and user-data policy.
