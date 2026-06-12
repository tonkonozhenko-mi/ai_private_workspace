# Model download job UX

Task 208 keeps the local model download flow calm and explicit.

## Product behavior

The UI presents model download as a short, user-owned flow:

1. Check installed local models.
2. Pick a recommended model.
3. Create a download draft.
4. Run the approved backend job only when execution is enabled.
5. Refresh installed models after success.

The default experience remains safe and non-surprising: if backend execution is disabled, users still get copy-only commands and a clear explanation.

## UX rules

- Do not show backend internals as the primary story.
- Show `Complete`, `Running`, `Queued`, or `Failed` instead of raw command states where possible.
- Hide backend output until a failure needs troubleshooting.
- Refresh installed models after a successful job so the user sees the result in the same place.
- Keep model downloads separate from indexing. Installing an embedding model must never trigger index rebuild automatically.

## Safety rules

- The frontend never executes shell commands.
- The backend job can only run when model download execution is explicitly enabled.
- Only backend-generated, catalog-allowlisted `ollama pull <model>` commands are eligible.
- Arbitrary user shell input is not accepted.
- MCP tools, scans, indexing, rebuilds, and restarts are not triggered by model download jobs.
