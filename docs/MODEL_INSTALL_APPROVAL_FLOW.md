# Model install approval flow

Task 203 adds the first safe step toward an in-app model download manager.

## Current behavior

The app can create a model download draft for a selected Ollama model. The draft records intent and gives the user a copyable command such as:

```bash
ollama pull nomic-embed-text
```

The draft is stored as a manual-only command proposal so it can be reviewed, rejected, or copied later.

## Safety boundary

This task intentionally does **not** download models from the frontend or backend.

- The frontend never runs shell commands.
- The backend records intent only.
- The generated command is marked `manual_only`.
- The draft is not auto-executable by policy.
- No scan, indexing, rebuild, restart, MCP tool, or agent execution is triggered.

## Future steps

The next implementation step can add a controlled backend download worker with an explicit allowlist:

1. User chooses a model.
2. App shows model purpose, estimated size, and disk/network impact.
3. User explicitly approves the download.
4. Backend runs only allowlisted `ollama pull <known-model>` commands.
5. App verifies availability through `ollama list` or Ollama API.
6. User chooses whether to save the model as a workspace preference.

Until that exists, model installation remains manual and transparent.
