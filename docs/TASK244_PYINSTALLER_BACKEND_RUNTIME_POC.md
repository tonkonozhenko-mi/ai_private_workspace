# Task 244 — PyInstaller backend runtime proof-of-concept

## Goal

Move Phase 22 from source runtime staging toward a real frozen backend runtime while keeping the desktop safety contract intact.

## Added

- `GET /runtime/pyinstaller-backend-runtime-contract`
- `backend/packaging/pyinstaller_backend_entrypoint.py`
- `backend/packaging/ai_private_workspace_backend.spec`
- `scripts/build_pyinstaller_backend_runtime.sh`
- `scripts/check_pyinstaller_backend_runtime.sh`
- `backend/tests/test_pyinstaller_backend_runtime_contract.py`
- Settings UI section: **PyInstaller backend runtime PoC**

## Why PyInstaller first

PyInstaller is a practical first frozen-runtime candidate because it is open-source, free, cross-platform, well-known in the Python ecosystem, and simpler to operate than a custom embedded Python runtime.

Fallbacks remain available:

- Nuitka, if PyInstaller dependency discovery becomes unreliable;
- packaged Python runtime, if full control is required;
- Electron shell, only if Tauri becomes too expensive for packaging/support.

## Safety contract

The build script does not start backend processes and does not run scan, index, rebuild, MCP, Agent, or model downloads.

Generated output stays under:

```text
build/desktop/frozen-backend-runtime
```

It must not be committed to GitHub or included in source release archives.

## Commands

Static/safe check:

```bash
scripts/check_pyinstaller_backend_runtime.sh
```

Build in a local packaging environment where PyInstaller is installed:

```bash
python3 -m pip install pyinstaller
scripts/build_pyinstaller_backend_runtime.sh
```

## Status

This task adds a reproducible PoC path. It does not yet claim signed/notarized macOS packaging, Windows installer completion, or production-grade frozen runtime QA.
