# Windows packaging foundation

Task 221 adds the Windows equivalent of the macOS desktop packaging path.

The final product goal is still:

```text
downloaded package -> double click -> local backend starts -> UI opens
```

For Windows, the packaging foundation uses:

- Tauri-first desktop shell direction;
- app data under `%LOCALAPPDATA%\AI Private Workspace`;
- logs under `%LOCALAPPDATA%\AI Private Workspace\logs`;
- backend health check at `http://127.0.0.1:8000/health`;
- app-owned backend process lifecycle;
- no frontend shell execution.

## Added scripts

- `scripts/windows_supervisor_contract.ps1`
- `scripts/package_windows_app_foundation.ps1`
- `scripts/prepare_windows_packaging_foundation.sh`

The shell helper validates the Windows packaging contracts from macOS/Linux CI-like environments without running PowerShell packaging.

## Safety rules

- React/frontend never runs PowerShell, cmd.exe, or shell commands.
- Windows desktop shell may start only packaged app-owned backend processes.
- The app must never kill unknown processes just because they use the expected port.
- Backend binds to `127.0.0.1` by default.
- Launch does not start scan, index, rebuild, MCP servers, agent workflows, or model downloads.
- Model downloads remain backend-side approved jobs with allowlisted models.
- Runtime data lives under LocalAppData and is not overwritten by app updates.

## Current limitation

This is not a signed Windows installer yet. It is the source-controlled foundation for the future `.exe` / `.msi` packaging path.
