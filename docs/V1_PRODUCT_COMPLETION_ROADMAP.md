# v1 Product Completion Roadmap

AI Private Workspace is currently a **v0.1 source release candidate**. It is useful for local demos and development, but it is not yet a finished commercial desktop product.

This document defines what “100% ready” means for the product.

## Current state: v0.1 source release candidate

Done:

- Local workspace creation and restore.
- Project scan and skill detection.
- File selection rules and context indexing.
- Ask with local context.
- Persistent conversations and answer history.
- Project reports and documentation generation.
- Local model manager foundation.
- Ollama installed-model detection and backend-approved download jobs.
- Safe Agent + MCP planning foundation.
- macOS and Windows desktop packaging foundation.
- GitHub-ready source repository structure.

Not done yet:

- Signed macOS `.dmg` or notarized `.app`.
- Windows `.msi` or production `.exe` installer.
- Frozen backend runtime binary.
- Persistent production-grade background job storage.
- Sandboxed Agent/MCP execution.
- Auto-update flow.

## Completion stages

| Stage | Goal | Status |
| --- | --- | --- |
| v0.1 source RC | Source repo, local demo, safety, docs, GitHub readiness | Current |
| v0.2 desktop runtime | Frozen backend runtime, stronger supervisor, persistent jobs | Next |
| v0.3 installers | macOS signed package and Windows installer foundation | Planned |
| v0.4 Agent/MCP read-only execution | Sandboxed read-only tool execution with audit logs | Planned |
| v0.5 controlled write execution | Allowlisted write actions with approval gates and rollback notes | Planned |
| v1.0 product | Installer, updates, stable runtime, polished UX, documented safe agent flows | Target |

## Remaining large work packages

### 1. Frozen backend runtime

The desktop app should not depend on a random local Python setup.

Expected work:

- Choose freeze strategy, likely PyInstaller or similar.
- Produce a backend executable or app-owned runtime bundle.
- Validate app-owned logs, data paths, and port handling.
- Keep runtime data outside app updates.

### 2. Production desktop installers

Expected work:

- macOS `.app` and `.dmg` packaging.
- Code signing and notarization path.
- Windows `.exe`/`.msi` packaging.
- Desktop shortcuts, app icons, logs, and uninstall behavior.

### 3. Persistent job system

Expected work:

- Persist model download jobs.
- Persist indexing/report/agent job state where useful.
- Recover friendly state after app restart.
- Keep cancellation semantics safe.

### 4. MCP server lifecycle

Expected work:

- Install/configure/check MCP servers.
- Show available tools and risk classes.
- Start servers backend-side only.
- Store logs and health state.
- Keep tools disabled until approval/sandbox rules exist.

### 5. Safe Agent execution

Expected work:

- Read-only execution first.
- Strict allowlist.
- Evidence and audit logs.
- No arbitrary shell from browser.
- Clear approval gates.
- Write actions only after rollback and verification design exists.

### 6. UX and product readiness

Expected work:

- Final human onboarding.
- Clean empty states.
- Better model hardware recommendations.
- Screenshots and demo assets.
- Release documentation.
- User-facing troubleshooting without developer jargon.

## Honest estimate

From the current v0.1 source RC to a polished v1.0 desktop product, expect roughly **15–25 large tasks**, depending on how deep Agent/MCP execution and installer quality should go.

The next practical target is **v0.2 desktop runtime**, not “all of v1.0 at once”.
