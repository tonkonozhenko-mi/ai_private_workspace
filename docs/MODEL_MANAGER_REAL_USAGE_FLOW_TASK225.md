# Task 225 — Model Manager real usage flow and render recovery

This task fixes the Models screen as a release blocker and makes the model workflow easier to understand.

## What changed

- Added defensive rendering around the Models screen so one unexpected response shape cannot blank the whole app.
- Hardened model install, job history, guided setup, and first-launch panels against missing arrays or optional fields.
- Added a calm `Model flow` section: Choose → Download → Verify → Use.
- Kept the safety model unchanged: the frontend never runs shell commands.

## User flow

1. Choose an AI answer model and a search context model.
2. Download missing models using copy-only commands or approved backend jobs.
3. Verify installed models through the read-only Ollama status check.
4. Ask questions with the chosen AI model.
5. Rebuild context only when the search context model changes.

## Safety boundaries

- No automatic model downloads.
- No frontend shell execution.
- Backend model jobs remain opt-in and allowlisted.
- Installing an embedding/search model does not automatically rebuild the index.


## Task 226 update

The recommended real-world flow is now visible in the Models tab:

1. Choose a hardware profile.
2. Use the recommended answer model for questions.
3. Use the recommended embedding model for search context.
4. Download missing models manually or through the approved backend job flow.
5. Refresh installed models.
6. Save one answer model and one search model for the workspace.

The frontend still never runs `ollama pull` directly.
