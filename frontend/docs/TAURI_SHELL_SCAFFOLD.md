# Tauri shell scaffold

Task 219 adds the first source-controlled Tauri shell foundation for AI Private Workspace.

## Goal

The product target is still:

```text
download package -> double click app -> local backend starts -> UI opens
```

This task does **not** create a final signed macOS installer. It creates the safe scaffold that lets the project move from bash-based app foundations toward a real desktop shell.

## Added source files

```text
frontend/src-tauri/tauri.conf.json
frontend/src-tauri/Cargo.toml
frontend/src-tauri/build.rs
frontend/src-tauri/src/main.rs
scripts/prepare_tauri_shell_scaffold.sh
```

## Safety boundary

The Tauri scaffold is intentionally minimal.

It does not:

- start scans;
- build search context;
- rebuild indexes;
- start MCP servers;
- execute agent workflows;
- download models;
- execute shell from React/frontend code.

Future backend startup must be implemented in the desktop shell/supervisor layer, not in React UI code.

## Validate scaffold

From project root:

```bash
./scripts/prepare_tauri_shell_scaffold.sh
```

The script checks that required scaffold files exist and that the current Rust entrypoint does not use direct process execution APIs.

## Next step

Implement a Tauri-owned backend supervisor bridge:

1. prepare app-owned data/log paths;
2. start only app-owned backend process;
3. bind backend to `127.0.0.1`;
4. poll `/health`;
5. open UI only after readiness;
6. stop only the PID owned by the app.

