# macOS backend runtime bundle plan

Task 218 moves packaging from a launcher-only `.app` foundation toward a real app-owned backend runtime.

The target is simple for the final user:

1. Download AI Private Workspace.
2. Double-click the app.
3. The desktop shell starts the local backend itself.
4. The UI opens after `/health` is ready.
5. No manual `venv`, `pip install`, or repo scripts are required.

## Current state

The generated `.app` foundation stages backend source and frontend static assets, then starts the backend through the supervisor-wired launcher. This is useful for validating lifecycle and safety, but it still relies on local `python3` and installed backend dependencies.

## Added in Task 218

- `scripts/prepare_macos_backend_runtime.sh`
- `GET /runtime/backend-runtime-bundle-plan`
- Runtime manifest at `build/macos/backend-runtime/AI_PRIVATE_WORKSPACE_RUNTIME_MANIFEST.txt`
- Package script preflight that generates and copies the runtime manifest into the app resources
- UI section in Settings under Desktop packaging

## Runtime manifest

The manifest records:

- Python version available during packaging
- backend requirements path
- requirements SHA256
- backend source file counts
- required runtime-data excludes
- safety rules for packaged updates

It is a foundation artifact, not the final frozen backend binary.

## Safety boundaries

Runtime preparation is an explicit packager/developer action. It does not start scan, index, rebuild, MCP, agent workflows, or model downloads.

Runtime data remains outside the app bundle. Generated packages must exclude:

- `backend/.ai-workbench/`
- `*.db`
- `*.sqlite`
- `*.sqlite3`
- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `frontend/node_modules/`
- `frontend/dist/`
- `build/`

## Next step

Choose the final backend runtime strategy after the manifest is stable:

- PyInstaller
- Nuitka
- packaged Python runtime

The next packaging task can then add the Tauri shell scaffold and map supervisor states to native startup UI.
