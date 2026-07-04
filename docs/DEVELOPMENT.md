# Development

Developer startup, validation, and source-hygiene rules. Product principles and
the contribution flow live in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Frontend

```bash
cd frontend
npm ci
npm run dev
```

## macOS launchers

Developer-safe launcher:

```bash
chmod +x scripts/launch_macos.command scripts/create_macos_shortcut.sh
./scripts/launch_macos.command
```

For the desktop app bundle, double-click `Open AI Private Workspace.command` in
the repository root. It rebuilds the packaged app when tracked application
sources changed since the last successful build, otherwise it opens the
existing app immediately and brings its window to the front.

When an update is detected while the app is already open, the launcher
smoke-checks the new backend on an isolated port, then asks the known app bundle
to close cleanly before opening the updated build. It never force-kills an
unknown process.

If the launcher cannot build or open the app, it keeps the Terminal window open
and points to `build/desktop/open-ai-private-workspace.log`. The packaged app
backend also writes diagnostics to:

```text
~/Library/Application Support/AI Private Workspace/logs/
```

## Validation

Run the release audit from the repository root:

```bash
./scripts/audit_release_candidate.sh
```

Run focused backend checks:

```bash
cd backend
pytest -q tests/test_final_product_status.py tests/test_product_completion_roadmap.py tests/test_release_candidate_audit.py tests/test_release_candidate_audit_script.py tests/test_source_release_archive_script.py tests/test_api_inventory.py
```

Run frontend validation:

```bash
cd frontend
npm ci
npm run build
```

Create a clean source archive:

```bash
./scripts/prepare_source_release_archive.sh
```

The generated archive is written to `build/release/` and must not be committed.

## Runtime data policy

Do not commit:

- `backend/.ai-workbench/`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`
- `.pytest_cache/`
- `__pycache__/`
- `*.db`, `*.sqlite`, `*.sqlite3`
