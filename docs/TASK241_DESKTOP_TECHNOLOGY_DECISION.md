# Task 241 — Desktop technology decision record

Task 241 makes the desktop shell choice explicit instead of treating it as a hidden implementation assumption.

## Decision state

Tauri is the current candidate for the v0.2 desktop runtime work, but it is not an irreversible v1.0 decision. It remains replaceable until one macOS and one Windows packaging proof pass with the frozen backend runtime.

## Why Tauri is the current candidate

- The existing React frontend can be reused for macOS and Windows.
- The desktop shell can stay smaller than typical Chromium-bundled Electron apps because it uses the system webview.
- Rust native commands are suitable for a narrow supervisor layer: status, log paths, health checks, and later app-owned backend startup.
- The current Tauri bridge is read-only. It does not start backend processes and does not give React shell execution.
- The target product is still local-first: downloaded package, double click, local backend, local UI, no external services.

## Alternatives considered

| Option | Status | Why not chosen as default now |
| --- | --- | --- |
| Tauri + React | Current candidate | Needs Rust/Tauri toolchain and real packaging validation before v1.0. |
| Electron + React | Fallback option | Mature, but larger app footprint and more hardening surface. |
| Native SwiftUI + WinUI | Not recommended for now | Best native feel, but creates separate macOS and Windows UI codebases. |
| Browser UI + launcher scripts | v0.1 baseline | Good for source RC, not a real double-click desktop product. |

## Guardrails

- Frontend must never gain arbitrary shell execution.
- Native commands must stay small, explicit, and allowlisted.
- Desktop launch must not trigger scan, index, rebuild, MCP, Agent, or model downloads.
- Tauri can be replaced before v1.0 if packaging, signing, webview, or maintenance cost becomes worse than alternatives.

## Added in this task

- `GET /runtime/desktop-technology-decision`
- Settings UI section: **Desktop shell technology decision**
- Backend test: `backend/tests/test_desktop_technology_decision.py`
