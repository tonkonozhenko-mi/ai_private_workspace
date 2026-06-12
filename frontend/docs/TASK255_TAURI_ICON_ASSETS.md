# Task 255 — Tauri icon assets

## Why this task exists

Local `cargo check --manifest-path src-tauri/Cargo.toml` failed because Tauri's `generate_context!()` macro could not read a valid icon asset:

```text
failed to open icon frontend/src-tauri/icons/icon.png
icon ... is not RGBA
```

Tauri validates icon assets during Rust compilation, so missing or non-RGBA PNG files break the desktop smoke path before the app can start.

## What changed

- Added required placeholder Tauri icons under `frontend/src-tauri/icons/`.
- Icons are valid 8-bit RGBA PNG files.
- Removed the unused `Path` import from `frontend/src-tauri/src/lib.rs`.
- Added `scripts/check_tauri_icon_assets.sh`.
- Added `GET /runtime/tauri-icon-assets`.
- Added regression tests for icon format and Rust import hygiene.

## Required local validation

```bash
scripts/check_tauri_icon_assets.sh
cd frontend
cargo check --manifest-path src-tauri/Cargo.toml
```

After this passes, continue with:

```bash
npm run tauri dev
```

## Safety

This task does not change startup semantics. Tauri app-owned backend startup remains gated by the frozen runtime manifest and HTTP `/health` readiness. No scan, index, rebuild, MCP, Agent, or model download starts automatically.
