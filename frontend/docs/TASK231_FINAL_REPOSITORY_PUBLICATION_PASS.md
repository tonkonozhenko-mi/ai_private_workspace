# Task 231 — Final repository publication pass

Task 231 stabilizes the project as a GitHub-ready v0.1 source release candidate.

## What changed

- Restored root-level repository presentation files:
  - `README.md`
  - `CONTRIBUTING.md`
  - `SECURITY.md`
  - `.editorconfig`
  - `.gitattributes`
- Added GitHub automation and community files:
  - `.github/workflows/ci.yml`
  - `.github/workflows/desktop-packaging-checks.yml`
  - `.github/pull_request_template.md`
  - `.github/ISSUE_TEMPLATE/bug_report.yml`
  - `.github/ISSUE_TEMPLATE/feature_request.yml`
- Kept source release expectations aligned with the audit script and GitHub publication checklist.

## Intent

The repository should look complete when opened on GitHub, not like an internal working folder. A visitor should immediately understand:

1. what AI Private Workspace is;
2. what is safe by design;
3. how to run it locally;
4. what v0.1 includes;
5. what is still future v1 work.

## Safety preserved

- No frontend shell execution was added.
- No automatic model, MCP, agent, scan, index, or rebuild execution was added.
- Runtime/build artifacts remain excluded from release archives.
- Desktop packaging remains foundation-level, not a signed installer claim.
