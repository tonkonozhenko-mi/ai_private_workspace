# Task 272 — Product goal UX, model skills, MCP, and dark theme hardening

Goal: move the app closer to the original idea: a simple local-first AI workspace for safe project work, not a developer dashboard.

## What changed

- Added a product goal panel: choose folder, build context, pick local model, approve tools.
- Added direct model catalog actions:
  - choose answer model for this workspace;
  - choose search model for this workspace;
  - apply recommended skill guidance when a model is selected.
- Added model-specific skill presets stored locally on this Mac.
  - Example: Qwen can use Developer guidance, Llama can use Documentation guidance, Mistral can use DevOps guidance.
- Reworked MCP/agent permissions into a simple explanation:
  - what MCP is;
  - what it can do;
  - approval-based modes for tools, file edits, and commands.
- Hardened dark theme with broad dark tokens and panel/input/select overrides.
- Hardened layout overflow for model cards, settings, Ask, permissions, and responsive grids.

## Product fit analysis

The app can now cover the core target flow:

1. user chooses a local project folder;
2. app scans files locally;
3. app builds local search context;
4. user chooses a local open-source model sized for their Mac;
5. user pairs the model with a useful work style/skill;
6. user asks questions with local sources attached;
7. advanced MCP/edit/command capabilities remain approval-gated.

Still not final product quality:

- MCP tools are explained and permission-gated in UI, but real non-technical MCP setup still needs a guided server wizard.
- Hardware-aware model recommendation is still mostly static; later it should read actual Mac memory/chip and rank models dynamically.
- File edit/apply flow should become inline preview/apply, not just permission text.

## Manual smoke

1. Open packaged app.
2. Switch to dark theme; no bright white panels should remain in Home, Ask, Models, Settings.
3. Open Models.
4. Confirm Product goal, Model catalog, Skills, Local model manager, and Tools/permissions are visible but not overwhelming.
5. Choose a model from Model catalog.
6. Save a skill preset for current model.
7. Reopen the app and confirm the UI still works.
8. Ask a question with local sources.

## Checks

```bash
./scripts/check_product_goal_ux_contracts.sh
cd frontend
npm run typecheck
npm run build
```
