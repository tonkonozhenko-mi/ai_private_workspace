# Task 252 — Packaging toolchain fixes

Task 252 fixes two local desktop-runtime blockers discovered during macOS smoke preparation.

## Fixed blockers

1. `scripts/build_pyinstaller_backend_runtime.sh` failed with a duplicated entrypoint path:

```text
backend/packaging/backend/packaging/pyinstaller_backend_entrypoint.py not found
```

The PyInstaller spec now resolves the backend entrypoint from `SPECPATH`, so the path is stable when PyInstaller executes the `.spec` file from its own directory.

2. `pyinstaller` was not declared in backend requirements.

`backend/requirements.txt` now includes:

```text
pyinstaller>=6.0,<7.0
```

## Cargo/Rust prerequisite

Tauri requires Rust/Cargo on the developer machine. This is an external toolchain prerequisite, not something the app installs or runs automatically.

On macOS, use one of these options:

```bash
brew install rust
```

or use rustup from the official Rust installer:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Then verify:

```bash
cargo --version
```

## New check

```bash
scripts/check_packaging_toolchain_prerequisites.sh
```

This validates:

- PyInstaller is declared in backend requirements;
- PyInstaller spec uses spec-relative path resolution;
- Tauri CLI is declared in `frontend/package.json`;
- Cargo availability is reported clearly.

## Safe local sequence

```bash
cd backend
python3 -m pip install -r requirements.txt
cd ..

scripts/check_packaging_toolchain_prerequisites.sh
scripts/build_pyinstaller_backend_runtime.sh
scripts/check_pyinstaller_backend_runtime.sh
scripts/smoke_frozen_backend_runtime.sh

cd frontend
npm ci
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri dev
```

## Safety

- Frontend still cannot execute shell commands.
- Toolchain installation is manual and developer-owned.
- PyInstaller build does not start scan/index/rebuild/MCP/Agent/model downloads.
- Generated `build/desktop/*` artifacts must not be committed.
