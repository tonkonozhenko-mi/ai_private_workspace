# Desktop supervisor contract

Task 216 defines the lifecycle contract for the real packaged desktop app.

The target user experience is still:

```text
Download package -> double click app -> local backend starts -> UI opens when ready
```

This task does not turn the frontend into a shell executor. It defines the app-owned supervisor that the future macOS/Windows package will use.

## Backend endpoint

```text
GET /runtime/desktop-supervisor-contract
```

The endpoint is read-only. It returns:

- startup states shown to the user;
- localhost/port rules;
- log paths;
- environment variables;
- shutdown rules;
- validation steps;
- safety boundaries.

## Development contract script

```bash
scripts/desktop_supervisor_contract.sh
```

The script is a development bridge for the future packaged app supervisor. It:

- starts only the app-owned backend;
- binds to `127.0.0.1`;
- waits for `/health`;
- writes supervisor/backend logs;
- refuses to kill unknown processes when the port is busy;
- stops only the backend PID that it started.

It does not:

- run scan/index/rebuild;
- download models;
- start MCP servers;
- execute agent tools;
- overwrite runtime data.

## Why this matters

The previous launch scripts were helpful for development, but the final product cannot expect users to know repo layout or terminal commands. The real app needs a supervisor layer owned by the desktop shell.

This task locks that contract before wiring it into the `.app` skeleton and later Windows package.
