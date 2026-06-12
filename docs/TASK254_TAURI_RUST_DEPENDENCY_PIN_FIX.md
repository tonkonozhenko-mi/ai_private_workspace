# Task 254 — Tauri Rust dependency pin fix

Task 254 fixes the local `cargo check` blocker seen on macOS:

```text
error[E0119]: conflicting implementations ... cookie-0.18.1 ... time ... HourBase
```

## Changes

- Pins `time = "=0.3.36"` in `frontend/src-tauri/Cargo.toml` until the upstream `cookie`/`time` dependency resolution is verified with a newer compatible stack.
- Adds `frontend/src-tauri/target/` to `.gitignore`.
- Excludes `frontend/src-tauri/target/` from release archive generation and audit database scans.
- Adds `scripts/check_tauri_rust_dependency_pins.sh`.
- Adds `GET /runtime/tauri-rust-dependency-pins`.

## Local fix commands

```bash
cd frontend
cargo update --manifest-path src-tauri/Cargo.toml -p time --precise 0.3.36
cargo check --manifest-path src-tauri/Cargo.toml
```

## Safety

This task does not add shell execution to the React frontend and does not start scan, index, rebuild, MCP, Agent, or model downloads.
