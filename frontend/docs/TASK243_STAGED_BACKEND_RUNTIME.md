# Task 243 — Staged Backend Runtime

Task 243 adds the first practical backend runtime staging layer for the
desktop app path.

## Why this matters

v0.1 is a source release candidate. v0.2 needs a desktop runtime that can later
be started by the desktop shell without requiring the user to manually assemble
backend files.

This task does not claim a final frozen binary. It creates the safer
intermediate step:

```text
source backend -> staged runtime directory -> manifest + launcher -> future frozen runtime
```

## Added files

- `scripts/stage_backend_runtime.sh`
- `scripts/check_staged_backend_runtime.sh`
- `backend/tests/test_staged_backend_runtime_contract.py`

## Runtime output

The staging script creates:

```text
build/desktop/backend-runtime/
  app/
    app/
      main.py
      ...
  requirements.txt
  run_backend.sh
  AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.json
```

`build/desktop/` is generated build output and must not be committed or included
in source release archives.

## Safety contract

- The staging command does not start the backend.
- The staging command does not scan, index, rebuild, start MCP, start Agent, or
  download models.
- The frontend only displays the commands/status; it does not execute them.
- Runtime data and logs stay outside the staged runtime and outside app bundles.
- The final v1.0 product still needs a frozen backend binary and signed
  installers.

## Validation

```bash
scripts/stage_backend_runtime.sh
scripts/check_staged_backend_runtime.sh
```

Targeted tests:

```bash
cd backend
python -m pytest -q tests/test_staged_backend_runtime_contract.py
```
