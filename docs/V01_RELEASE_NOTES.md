# v0.1 Release Notes

## Release label

**AI Private Workspace v0.1 — local-first release candidate**

## What is included

- Workspace onboarding and local project selection.
- Project scan and skill detection.
- File selection and indexing control.
- Local RAG-style Ask flow.
- Persistent conversations and answer history.
- Project reports and documentation generation.
- Guided local model setup.
- Installed model detection.
- Safe model download drafts, backend-owned jobs, status, history, and cancel-safe semantics.
- Agent planning and MCP setup UX foundation.
- macOS app foundation, supervisor contract, and Tauri scaffold.
- Windows packaging foundation.
- Release candidate audit script and docs.

## Safety boundaries

- Frontend never executes shell commands.
- App launch does not trigger scan, index, rebuild, MCP, Agent, or model downloads.
- Model downloads are backend-side, opt-in, allowlisted, and user-approved.
- Agent and MCP execution remain disabled until sandbox/allowlist execution exists.
- Runtime data and build artifacts are excluded from source handoff archives.

## Known limitations

- v0.1 is a source handoff / release candidate, not a final signed installer.
- Tauri shell exists as scaffold/foundation.
- Backend runtime freeze/bundle is not final.
- Windows `.exe/.msi` packaging is foundation only.
- Agent/MCP execution is intentionally not implemented yet.

## Recommended next milestone

Move from source handoff to installer-grade desktop app:

1. Finalize Tauri backend supervisor execution.
2. Bundle/freeze backend runtime.
3. Produce signed macOS package.
4. Produce Windows installer.
5. Add sandboxed Agent/MCP execution only after strict safety gates.
