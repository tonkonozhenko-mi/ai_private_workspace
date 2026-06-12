# Task 269 — Daily-use MVP polish

## Goal

Turn the packaged smoke build into a workspace that is easier to use every day, without adding unsafe automation.

The focus is not new advanced AI features. The focus is making the current flow obvious:

1. open the packaged app;
2. select or create a workspace;
3. scan;
4. build search context;
5. ask;
6. restart;
7. continue from persisted workspace/index/conversation state.

## What changed

### 1. Daily-use readiness panel

The Overview tab now has a `Use it now` panel that explains the next useful action without forcing the user to search through many sections.

It shows four checks:

- Project scan
- Search context
- Models
- Ask history

The primary button changes depending on the workspace state:

- `Scan project`
- `Build search context`
- `Fix model setup`
- `Ask this workspace`

### 2. Ask conversation restore

When the Ask tab opens, the frontend reloads the latest conversation for the selected workspace when one exists. This makes app restart feel continuous instead of showing an empty Ask screen while the history exists elsewhere.

### 3. Safety stays unchanged

The new UI does not run shell commands and does not auto-start scan/index/ask on mount.

The user still has to explicitly click:

- scan;
- index;
- ask.

### 4. Daily-use contract check

Added:

```bash
./scripts/check_daily_use_mvp_contracts.sh
```

It checks:

- Overview has an obvious daily-use panel;
- scan/index/ask actions are visible;
- Ask restores latest conversation state;
- frontend still has no shell/model-pull execution;
- scan/index/ask are not auto-fired from mount effects.

## Manual packaged smoke

```bash
./scripts/audit_release_candidate.sh
./scripts/check_packaged_app_workspace_api_smoke.sh
./scripts/check_packaged_app_full_flow_contracts.sh
./scripts/check_packaged_app_persistent_rag_contracts.sh
./scripts/check_runtime_readiness_ux_contracts.sh
./scripts/check_daily_use_mvp_contracts.sh

cd backend
python3 -m pytest -q

cd ../frontend
npm ci
npm run typecheck
npm run build
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri:build
open "src-tauri/target/release/bundle/macos/AI Private Workspace.app"
```

In the app:

1. Open Overview.
2. Confirm `Use it now` is visible near the top.
3. Confirm it shows the real next action.
4. Scan if needed.
5. Build search context if needed.
6. Fix Models if needed.
7. Ask a question.
8. Quit the app.
9. Reopen the app.
10. Open Ask and confirm the latest conversation is restored.
11. Ask again without reindex when persistent vector store is already built.

## Acceptance criteria

- Overview clearly says what to do next.
- User does not need to search through many sections for the basic flow.
- Ask history/conversation continuity is visible after restart.
- No hidden scan/index/ask automation.
- No frontend shell execution.
- Existing packaged startup/runtime safety remains unchanged.
