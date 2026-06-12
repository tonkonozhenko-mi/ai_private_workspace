# Task 266 — Packaged Full Product Flow Smoke

## Purpose

This gate proves the first complete packaged macOS product path:

`open .app -> create workspace -> scan -> index -> ask -> quit -> reopen`

All project actions remain explicit. Desktop startup starts only the app-owned
frozen backend. It never starts scan, index, Ask, model downloads, MCP, or
Agent workflows.

## Build And Static Checks

```bash
./scripts/build_pyinstaller_backend_runtime.sh
./scripts/check_pyinstaller_backend_runtime.sh
./scripts/smoke_frozen_backend_runtime.sh
./scripts/audit_release_candidate.sh
./scripts/check_packaged_app_workspace_api_smoke.sh
./scripts/check_packaged_app_full_flow_contracts.sh

cd backend
python3 -m pytest -q

cd ../frontend
npm ci
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

## Manual UI Smoke

1. Open the packaged `.app`.
2. Confirm the desktop backend reports healthy.
3. On a clean data directory, confirm the first-run state says no projects yet.
4. Add a local project and select it.
5. Click **Scan project**, review the file preview, then explicitly confirm.
6. Confirm detected files and skills appear.
7. Click **Build search context**, review the file preview, then explicitly confirm.
8. Confirm index status and chunk count appear.
9. Select a supported local or deterministic smoke LLM if the workspace has no selected LLM.
10. In Ask, submit `What is this project about?`.
11. Confirm an answer with local sources, or a clear runtime/index diagnostic.
12. Quit the app.
13. Confirm port 8000 is released and no app-owned backend remains.
14. Reopen the app.
15. Confirm workspace, latest scan, and index metadata still appear.
16. Ask again. With `VECTOR_STORE=memory`, expect a clear missing-active-chunks
    diagnostic after restart and explicitly rebuild context. With Qdrant, the
    indexed chunks should remain available.

## Manual Terminal Checks

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/workspaces/overview

ls -la "$HOME/Library/Application Support/AI Private Workspace/data"
ls -la "$HOME/Library/Application Support/AI Private Workspace/logs"

tail -n 150 "$HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log"
tail -n 150 "$HOME/Library/Application Support/AI Private Workspace/logs/backend.log"
```

## Expected Logs

`backend.log` records:

- workspace job queued/started/completed/failed with workspace ID and job type;
- Ask requested/completed/rejected with workspace ID;
- Ask provider/model, retrieved chunk count, diagnostic code, and quality warning count.

Question text and project file contents are not added to these lifecycle logs.

## Persistence Boundary

SQLite persists workspace metadata, latest scan, index status, model selection,
timeline, and conversations. The default in-memory vector store does not
persist chunks across backend restarts. This is reported explicitly rather than
silently pretending Ask context survived. Qdrant is the persistent vector-store
option.

## Verified Local Result — Task 266

The rebuilt macOS `.app` was opened against the app-owned database at:

```text
~/Library/Application Support/AI Private Workspace/data/workspaces.db
```

Verified packaged flow:

- `/health` and `/workspaces/overview` returned HTTP 200 after `.app` open;
- a fresh `Task 266 Packaged Full Flow` workspace was created through the
  packaged API used by the UI;
- the new workspace survived quit/reopen and remained first in overview;
- explicit scan completed in 4 ms with `1` scanned file and `1` detected skill;
- explicit index completed in 6 ms with `1` indexed file and `1` chunk;
- explicit Ask using selected `fake/fake-llm` returned one local source:
  `README.md`, score `0.40422604172722165`;
- after quit/reopen, workspace, scan, selected LLM, and index metadata persisted;
- the first Ask after restart returned
  `index_metadata_exists_but_no_chunks_found`, which is correct for
  `VECTOR_STORE=memory`;
- after an explicit reindex, Ask again returned the local `README.md` source;
- graceful quit released port 8000 and left no AI Private Workspace process.

The deterministic fake answer also produced the expected medium quality
warning `answer_missing_source_paths`. This is a useful guardrail: the source
was retrieved, but the fake answer text did not cite its path.

## Safety Contract

- Frontend calls backend APIs; it does not execute shell commands.
- Scan, index, and Ask start only after explicit user actions.
- Tauri starts only the app-owned frozen backend.
- Shutdown targets only the exact app-owned child PID.
- No kill-by-port, `pkill`, `killall`, or `taskkill`.
- No automatic model download or external project-content request.
