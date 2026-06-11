# Source Release Checklist

A source release archive should preserve the project root structure while excluding local runtime and build artifacts.

## Required root structure

```text
backend/
frontend/
docs/
scripts/
.github/
README.md
CONTRIBUTING.md
SECURITY.md
pytest.ini
.gitignore
```

## Excluded from release archives

```text
backend/.ai-workbench/
*.db
*.sqlite
*.sqlite3
frontend/node_modules/
frontend/dist/
build/
.venv/
__pycache__/
.pytest_cache/
```

## Build archive

```bash
./scripts/prepare_source_release_archive.sh
```

## Validate archive contents

```bash
unzip -l build/release/ai-private-workspace-v0.1-source.zip | head -80
```

The archive should look like a clean GitHub source checkout, not a local machine snapshot.
