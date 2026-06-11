# v0.1 Demo Handoff

This document describes the final v0.1 demo path for **AI Private Workspace**.

## Demo story

AI Private Workspace is a local-first desktop-like product for safely understanding a private project. The user chooses a local folder, scans it, builds local context, asks grounded questions, generates reports, manages local models, and prepares safe Agent/MCP plans.

The key message:

> The user stays in control. Nothing risky starts automatically.

## Demo flow

1. **Open the app**
   - Use the current local launcher or macOS `.app` foundation.
   - Expected: backend health is ready and UI opens.
   - Nothing scans, indexes, downloads, or executes automatically.

2. **Create or select a workspace**
   - Choose a local project folder.
   - Pick an assistant mode.
   - Expected: Overview shows the next safe action.

3. **Scan the project**
   - Start scan by explicit click.
   - Expected: detected technologies and files appear.

4. **Build search context**
   - Index selected files by explicit click.
   - Expected: Ask can use retrieved local context.

5. **Ask a project question**
   - Ask something practical like: “Explain this project structure and where deployment config lives.”
   - Expected: answer uses retrieved sources and avoids unsupported claims.

6. **Generate a report**
   - Create a project overview/report.
   - Expected: report is saved locally.

7. **Review local models**
   - Show LLM model vs embedding model.
   - Show installed/missing models.
   - Expected: downloads are backend-owned jobs and disabled by default unless explicitly enabled.

8. **Create safe Agent/MCP plan**
   - Create a manual/safe plan.
   - Review possible tools and approvals.
   - Expected: no automatic execution.

## Demo checkpoints

- Overview does not look overloaded.
- Advanced details are behind disclosure sections.
- Dark and light themes are readable.
- Risky actions are explicit.
- Model manager explains what is installed and what is missing.
- Agent/MCP is clearly “planning first, execution later”.

## Validation commands

```bash
./scripts/audit_release_candidate.sh
cd backend && pytest -q tests/test_v01_handoff.py tests/test_release_candidate_audit.py tests/test_api_inventory.py
cd frontend && npm ci && npm run build
```
