# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Respect `.gitignore` when indexing.** The scanner now honors the project's
  own `.gitignore` (accurate `pathspec` engine when available, built-in fallback
  otherwise) plus depth-agnostic exclude patterns, so virtualenvs,
  `node_modules`, build output, caches, and local `.env` files stay out of the
  local index.
- **Role-aware deep analysis.** The project summary and risks are now retrieved
  and written through the workspace's selected role lens (Tester, DevOps,
  Developer, Business analyst, …), not just a generic pass.
- **Home "Project activity" card** from read-only git history: last commit,
  commit counts, contributors, project age, and 90-day most-changed files.
- **Grounded guide cards on Home:** Architecture at a glance, Where to start
  (reading order), and How to run (commands found in the project's own files).
- **TODOs & loose ends card** — a deterministic inventory of
  TODO/FIXME/HACK/XXX/BUG markers read verbatim from project files.
- **Stop control** during scanning/indexing in the setup flow.
- `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, and a repository funding config.

### Changed

- Reset is now two clearly scoped actions: **Reset settings** (preferences to
  defaults, projects kept) and **Reset projects & data** (workspaces and index
  removed, settings kept). Project files on disk and installed models are never
  touched.
- The lighter `llama3.2` is the default first-run answer model.
- Removed the misleading "Confluence / Jira — coming soon" source cards.
- Backend now reports its version in the FastAPI/OpenAPI schema.

### Fixed

- **Answer creativity** is now observable: "Precise" sends temperature `0.0`, so
  the same question yields the same answer; "Creative" widens to `1.0`.
- Oversized "Save skill for this model" button and assorted spacing, font, and
  button-sizing inconsistencies across Home, Models, and Settings.
- Install/build-context flows no longer require multiple clicks; setup no longer
  prompts for folder access on a cold launch.

## [0.1.0] - 2026-06

Initial local-first release candidate: workspace onboarding, project scan and
skill detection, local RAG Ask flow, persistent conversations, guided local
model setup, safe model-download drafts, Agent/MCP planning UX, and the macOS +
Tauri packaging foundation. See
[docs/V01_RELEASE_NOTES.md](docs/V01_RELEASE_NOTES.md) for the full list.

[Unreleased]: https://github.com/tonkonozhenko-mi/ai_private_workspace/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tonkonozhenko-mi/ai_private_workspace/releases/tag/v0.1.0
