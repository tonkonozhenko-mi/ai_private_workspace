# Repo health audit — 2026-06-23

A pass over dead code, comments, best practices, tests, and docs. What was fixed
is committed; what needs your decision is flagged below.

## Summary

The repository is in good shape. Git is clean (no tracked build artifacts,
caches, `.DS_Store`, or IDE files — `.gitignore` covers them). The backend has
essentially **no dead code**: every module is reachable through dependency
injection, route registration, or tests. Comments are purposeful — there are
**zero** `TODO`/`FIXME`/`HACK` markers in `backend/app` or `frontend/src`, and no
abandoned commented-out code blocks.

## Fixed in this pass

- **Removed 52 unused TypeScript types** in `frontend/src/api/types.ts` that
  mirrored internal packaging/desktop/V01 docs and were never consumed by the UI.
  Verified by the type-checker: removal compiles clean, proving zero real usage.
- **CI test report is now visible.** `pytest` writes JUnit XML; a stdlib-only
  script (`scripts/ci_test_summary.py`) renders a pass/fail/skip table to each
  CI run's page, and the JUnit file is uploaded as an artifact. No third-party
  actions, no extra permissions.
- **Docs actualized.** README documents the new role dashboard, human-readable
  risks, and CI/CD flow; notes that it tracks `main` (ahead of the latest
  release); and describes the test suite + CI reporting.

## Tests

- **Backend: strong.** ~645 tests across 165 files, covering domain, use cases,
  and API, run on every push/PR.
- **Frontend: the gap.** There are **no** frontend tests. The type-checker and
  build run in CI, which catches type and compile errors, but there is no unit or
  component testing of React logic. Recommendation: add a light Vitest +
  Testing-Library setup and start with the pure helpers (formatters, the
  role-brief/risk rendering, command-palette filtering). This is the single
  biggest testing improvement available.

## Flagged for your decision (not changed)

1. **The Investigator has no UI.** The README documents "The Investigator" as a
   headline feature and the backend endpoint + `investigateProject()` client
   function exist, but there is **no Investigate tab** in the app
   (`WorkspaceTab` has none, and there is no Investigate component). Either wire
   it back into the UI, or stop presenting it as a current feature in the README.
   The unused `investigateProject` / `stopLlamaRuntime` client functions were
   left in place precisely because they map to real, intended capabilities —
   deleting them is a product decision, not cleanup.

2. **A few god-files.** The largest source files are very large and would be
   easier to maintain if split: `frontend/src/components/ModelsDetail.tsx`
   (~5,900 lines), `backend/app/api/routes/workspaces.py` (~3,400),
   `frontend/src/components/AskWorkspace.tsx` (~3,000), `api/routes/models.py`
   (~1,400), `api/dependencies.py` (~780). This is the main code-health item, but
   splitting them is a sizable, risky refactor — best done deliberately, one file
   at a time, with the tests as a safety net, rather than as a bulk cleanup.
   (Two of these are already tracked as pending refactors.)

3. **Some dead CSS likely exists** (e.g. leftover `skill-template-*`,
   `startup-checklist-*` blocks), but CSS has no compiler safety net and several
   classes are built dynamically (`status-badge--${tone}`,
   `workspace-engine-pill--${engine}`), so an automated sweep is unsafe. Worth a
   careful manual pass later; not worth the risk of breaking a live class now.

4. **`docs/` carries ~30 internal engineering notes** (packaging, smoke runbooks,
   V01 handoffs). They are fine to keep, but they are where the older "agent/MCP"
   framing still lives; if you want the public story fully consistent with the
   read-only direction, that's the place to revise next.
