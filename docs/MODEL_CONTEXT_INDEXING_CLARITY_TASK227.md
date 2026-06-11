# Task 227 — Model context indexing clarity

This pass fixes a confusing model setup state.

## Problem

After a user selected and saved the search/embedding model, the UI could still say that the workspace needed **Embedding Setup**. That was technically true only in a broad sense, but it was confusing because the selected search model already matched the active backend runtime.

The missing step was not model selection. The missing step was building searchable workspace context with that selected embedding model.

## Updated user language

The app now distinguishes these states:

- `needs_embedding_runtime` — the selected search model differs from the active backend runtime and needs runtime review/restart.
- `needs_context_index` — the selected search model matches the backend runtime, but the workspace context has not been indexed with it yet.
- `ready` — both the AI answer model and the search context are usable.

## UX rule

Do not tell the user to "set up embedding" when the model is already selected and active. Tell them to build or rebuild workspace context.

## Safety

This change does not start indexing automatically. It only clarifies the next action. Context building stays an explicit user-click action.
