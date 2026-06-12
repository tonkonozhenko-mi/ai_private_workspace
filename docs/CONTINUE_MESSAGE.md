# Continue message — AI Private Workspace

I continue the `ai_workspace` project — a local-first AI Private Workspace product.

Working style:

- Continue step-by-step through Tasks.
- User uploads a root-preserving zip of the whole project.
- ChatGPT modifies files and returns an updated root-preserving zip + patch.
- Keep the root structure: `backend/`, `frontend/`, `docs/`, `scripts/`, `.github/`, root docs/config files.
- Do not include runtime/build data in archives: `backend/.ai-workbench`, `.venv`, `node_modules`, `dist`, `build/`, caches, `*.db`, `*.sqlite`, `*.sqlite3`, `*.tsbuildinfo`.
- Answer in Russian, concise, with exact commands.
- Prefer larger useful tasks instead of many tiny tasks.
- Preserve safety rules.

Hard safety rules:

- Frontend/React never executes shell commands.
- Frontend does not auto-start scan/index/rebuild/restart/model downloads/MCP/Agent.
- Backend clean architecture: core without FastAPI/sqlite3; adapters in infrastructure.
- Model downloads are backend-side, opt-in, allowlisted, explicit approval only.
- MCP servers/tools do not start automatically.
- Agent workflows remain approval-gated; no automatic tool execution.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.
- Tauri may start only an app-owned backend executable from the frozen runtime manifest.
- Shutdown must be PID-owned; never kill unknown processes by port.

Current roadmap status:

- Phase 21 / v0.1 source RC: effectively complete.
- Phase 22 / v0.2 desktop runtime foundation: strongly in progress.
- Current latest task: Task 249 — macOS frozen runtime and Tauri smoke runbook.
- v0.1 publication remaining: 0–1 large task, mostly local manual UI smoke-check + source archive + GitHub push.
- v1.0 remaining: about 7–12 large tasks, depending on PyInstaller/Tauri/macOS/Windows issues found locally.

Recent important tasks:

- Task 243: staged backend runtime layout.
- Task 244: PyInstaller backend runtime PoC.
- Task 245: fixed Settings release audit crash, added frozen runtime selection, fixed frontend chunk warning.
- Task 246: frozen backend smoke contract.
- Task 247: fixed Settings `/runtime/v0.1-handoff` crash, added app-owned backend startup gate.
- Task 248: real gated Tauri app-owned backend startup implementation.
- Task 249: macOS frozen runtime + Tauri smoke runbook/checks + updated continue message.

Current desktop stack decision:

- Tauri + React + TypeScript + Vite for cross-platform desktop shell.
- FastAPI backend.
- PyInstaller first for frozen backend runtime.
- SQLite/Qdrant/Ollama local runtime pieces.
- Open-source/free, macOS + Windows, lightweight, maintainable, production-grade direction.
- Fallbacks remain possible if Tauri/PyInstaller becomes too painful: Nuitka, packaged Python runtime, Electron.

Next recommended task:

Task 250 — local smoke feedback/fixes. If the user ran local commands and shows errors, fix them first. Otherwise add Windows frozen runtime parity checks and keep moving toward installer-grade v1.0.

Task 250 — Tauri backend health readiness gate ✅

- Added `/runtime/app-owned-backend-health-readiness`.
- Added `scripts/check_tauri_backend_health_readiness.sh`.
- Tauri no longer treats open TCP port as readiness; startup success requires HTTP `GET /health` 200.
- Failed readiness cleanup stops only the child process started by this app session.
- No kill-by-port, no generic shell execution, no scan/index/rebuild/MCP/Agent/model downloads on launch.
- Next recommended large task: local macOS cargo/PyInstaller/Tauri smoke fixes, then Windows parity.
