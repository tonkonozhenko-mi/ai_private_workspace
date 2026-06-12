# Task 271 — Product UX cleanup and local model catalog

## Goal
Make the packaged MVP feel closer to a real local-first desktop product instead of a developer dashboard.

## Changes

- Ask is lighter: guidance is collapsed, composer text is shorter, and the main action stays focused on asking questions.
- Settings is reduced to daily-use preferences only: appearance, project file rules, and selected Ask guidance.
- Ask guidance now shows only the selected template and its active guidance instead of rendering every assistant style at once.
- Models includes a local model catalog for common open-source models:
  - Qwen2.5 Coder 7B
  - Llama 3.2 3B
  - Mistral 7B
  - Gemma 2 9B
  - Nomic Embed Text
  - mxbai Embed Large
- The catalog explains which models fit smaller and larger Macs so users do not pick unrealistic 70B/120B models by accident.
- MCP and agent/computer-control style capabilities are preserved as approval-based permissions instead of disappearing or cluttering the main flow.
- Layout overrides reduce overflow, clipped cards, uneven buttons, long model/path wrapping issues, and dark-theme surface problems.
- Added `scripts/check_daily_use_product_ux_contracts.sh`.

## Manual UI smoke

1. Open the packaged app.
2. Check Home: no visual clipping in ready card actions.
3. Open Ask: composer should be compact, guidance collapsed, and examples not visually heavy.
4. Ask a question and confirm history still appears after restart.
5. Open Models: local model catalog should explain Qwen, Llama, Mistral, Gemma and search models.
6. Open model advanced selection: cards must not overflow horizontally.
7. Open Settings: no redundant Models shortcut, no release/GitHub/runbook noise.
8. In Ask guidance, select a template; only the relevant guidance should be shown.
9. Toggle dark theme and confirm cards/inputs remain readable.

## Checks

```bash
./scripts/check_daily_use_product_ux_contracts.sh
cd backend && python3 -m pytest -q
cd ../frontend && npm ci && npm run typecheck && npm run build
```
