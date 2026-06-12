# Task 267 — Packaged Persistent RAG Smoke

## Goal

Make the packaged macOS `.app` keep indexed RAG chunks after quit/reopen. Task 266 proved the full flow works, but `VECTOR_STORE=memory` meant Ask could lose chunks after backend restart and return `index_metadata_exists_but_no_chunks_found`.

## Design

The packaged app now defaults to a simple app-owned SQLite vector store:

- Provider: `VECTOR_STORE=sqlite`
- Path: `~/Library/Application Support/AI Private Workspace/data/vector_store.db`
- Workspace DB remains: `~/Library/Application Support/AI Private Workspace/data/workspaces.db`

Qdrant remains available for advanced/local runtime setups. The memory vector store remains available for tests and fast dev runs, but it is no longer the packaged default.

## Persistence contract

The SQLite vector store persists:

- `workspace_id`
- `chunk_id`
- `source_path`
- `chunk_index`
- `content`
- `token_estimate`
- metadata JSON
- embedding JSON
- embedding provider/model/dimension
- created/updated timestamps

Reindex uses SQLite upsert by `(workspace_id, chunk_id)` to avoid duplicate chunks. Index still clears the workspace before writing the new set.

## Manual packaged smoke

```bash
./scripts/build_pyinstaller_backend_runtime.sh
./scripts/check_pyinstaller_backend_runtime.sh
./scripts/smoke_frozen_backend_runtime.sh
cd frontend
npm ci
npm run build
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

Then verify:

1. Open packaged `.app`.
2. Create a workspace/project.
3. Run Scan.
4. Run Index.
5. Ask: `What is this project about?`
6. Confirm answer has a local source.
7. Quit `.app`.
8. Confirm port 8000 is released.
9. Reopen `.app`.
10. Ask again without reindexing.
11. Confirm the answer still has local source chunks.
12. Confirm `index_metadata_exists_but_no_chunks_found` does not appear for an indexed workspace.

Terminal checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/workspaces/overview
ls -la "$HOME/Library/Application Support/AI Private Workspace/data"
tail -n 150 "$HOME/Library/Application Support/AI Private Workspace/logs/backend.log"
tail -n 150 "$HOME/Library/Application Support/AI Private Workspace/logs/desktop-supervisor.log"
```

Expected files:

```text
~/Library/Application Support/AI Private Workspace/data/workspaces.db
~/Library/Application Support/AI Private Workspace/data/vector_store.db
```

## Automated checks

```bash
./scripts/audit_release_candidate.sh
./scripts/check_packaged_app_workspace_api_smoke.sh
./scripts/check_packaged_app_full_flow_contracts.sh
./scripts/check_packaged_app_persistent_rag_contracts.sh
cd backend && python3 -m pytest -q
cd ../frontend && npm run typecheck && npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri:build
```

## Acceptance criteria

- Packaged `.app` does not default to `VECTOR_STORE=memory`.
- Indexed chunks survive backend restart.
- Ask after quit/reopen works without reindex.
- Persistent vector data lives under app-owned data dir.
- No writes inside `.app/Contents/Resources`.
- No automatic scan/index/model download on startup.
- No kill-by-port/pkill/killall/taskkill.
