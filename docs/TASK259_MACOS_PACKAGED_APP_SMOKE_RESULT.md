# Task 259 — macOS packaged app smoke result

Task 259 records the first successful local macOS desktop packaging milestone:

- `scripts/smoke_frozen_backend_runtime.sh` started the frozen backend runtime and returned `health ok: ok`.
- `cd frontend && npm run tauri:build` built `AI Private Workspace.app` successfully.
- The remaining macOS gate is opening the generated `.app` and validating app-owned backend startup, logs, and shutdown behavior.

## Fixes

`check_pyinstaller_backend_runtime.sh` was updated because it still expected the older `uvicorn.run("app.main:app")` entrypoint style. The current hardened entrypoint intentionally imports `app.main:app` first and then calls `uvicorn.run(app, ...)` so frozen startup import errors are visible.

The same check now allows generated binaries only in generated locations:

- `build/`
- `frontend/src-tauri/target/`

Any generated backend executable outside those locations remains a blocker.

## Local validation

```bash
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm run tauri:build
```

Optional packaged app smoke:

```bash
open frontend/src-tauri/target/release/bundle/macos/AI\ Private\ Workspace.app
```

## Safety

Generated binaries, manifests, smoke logs, `.app` bundles, and Rust target output remain local-only artifacts. They must not be committed or included in source release archives.
