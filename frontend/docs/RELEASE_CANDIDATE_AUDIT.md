# Release candidate audit

Task 222 adds a final read-only audit layer before the v0.1 handoff.

The audit is not a build system and does not launch AI workloads. It checks that the project is still safe to package and hand off:

- expected root structure is present;
- runtime data is not included in the source archive;
- key packaging and operator docs exist;
- safety boundaries are still explicit;
- local scripts have valid shell syntax;
- macOS, Windows, model manager, MCP, and Agent work remain opt-in.

Run from the project root:

```bash
./scripts/audit_release_candidate.sh
```

The script allows warnings for local developer artifacts such as `build/` or `frontend/dist`, because those may exist on a developer machine. They must still be excluded from generated handoff archives.

The release source archive should keep this structure:

```text
backend/
frontend/
docs/
scripts/
pytest.ini
.gitignore
```

Do not include:

```text
backend/.ai-workbench/
*.db
*.sqlite
node_modules/
dist/
build/
__pycache__/
.pytest_cache/
```

A release candidate is acceptable when the backend audit endpoint reports `review` or `ready` with no blocked items, frontend build passes, targeted backend tests pass, and the user-facing demo flow is documented.
