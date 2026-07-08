# Certification & badges

This project pursues the free, recognized open-source compliance badges. None of
them is a paid legal certification (ISO, SOC 2, GDPR audits cost money and need a
third-party auditor) — they are self-attested or automated signals that the
project follows security, licensing, and quality best practices.

What this repository already ships for them:

- **OpenSSF Scorecard** — `.github/workflows/scorecard.yml` (weekly + on push). Publishes results to the public OpenSSF API so the README badge stays live.
- **CodeQL** — `.github/workflows/codeql.yml`. Free static analysis (SAST) for the Python backend and the TS/JS frontend; also feeds the Scorecard "SAST" check.
- **REUSE** — `REUSE.toml` + `LICENSES/Apache-2.0.txt` + `.github/workflows/reuse.yml`. Machine-readable copyright/licensing for every file.
- **CodeFactor** — README badge (no workflow needed; it runs on CodeFactor's side).
- **OpenSSF Best Practices** — answer sheet below; the badge is added after you register the project.

All GitHub Actions are pinned to commit SHAs (with a `# version` comment), which
the Scorecard "Pinned-Dependencies" check rewards. Dependabot's `github-actions`
ecosystem keeps them updated.

---

## What you need to do by hand

Each of these needs your GitHub account once; after that they run themselves.

### 1. OpenSSF Scorecard

1. Push these changes to `main`.
2. In the repo: **Settings → Code security** → enable **Code scanning** (so the SARIF upload has somewhere to go).
3. The `Scorecard supply-chain security` workflow runs on push and weekly. After the first successful run with `publish_results: true`, the README badge goes live at `scorecard.dev`.
4. To raise the score further, enable **branch protection** on `main` (Settings → Branches → Add rule): require a PR and at least one review. Scorecard's "Branch-Protection" and "Code-Review" checks reward this.

### 2. CodeFactor

1. Go to <https://www.codefactor.io>, sign in with GitHub.
2. **Add repository** → select `ai_private_workspace`.
3. CodeFactor analyzes immediately; the README badge becomes live (grade A–F). No file changes required.

### 3. REUSE

1. Push to `main`. The `REUSE compliance` workflow runs `reuse lint` on every push/PR.
2. The badge at `api.reuse.software` picks the repo up automatically once it's public — no registration needed.
3. If the lint ever fails, run `pipx run reuse lint` locally to see which file lacks copyright/license info, then extend `REUSE.toml`.

### 4. OpenSSF Best Practices (the big one)

1. Go to <https://www.bestpractices.dev>, click **Get Your Badge Now!**, log in with GitHub.
2. Select `ai_private_workspace`. You get a numeric **project ID**.
3. Work through the questionnaire — use the **answer sheet below**; most criteria are already met by this repo.
4. Once you reach **Passing**, add the badge to the README (replace `PROJECT_ID`):

   ```markdown
   [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/PROJECT_ID/badge)](https://www.bestpractices.dev/projects/PROJECT_ID)
   ```

---

## OpenSSF Best Practices — passing-level answer sheet

Evidence in this repo for each criterion group. ✅ = already satisfied, ⚠️ = a
one-time action on your side (usually a GitHub setting, not code).

### Basics

- **Project homepage / description** ✅ — `README.md` describes what the software does.
- **Homepage & repo served over HTTPS** ✅ — GitHub.
- **Interaction (issues/PRs) documented** ✅ — `CONTRIBUTING.md`, issue templates in `.github/ISSUE_TEMPLATE/`, PR template.
- **Accepts contributions** ✅ — `CONTRIBUTING.md`.
- **Free/open license, OSI-approved** ✅ — `LICENSE` (Apache-2.0), machine-readable via `REUSE.toml`.
- **License in standard location** ✅ — `LICENSE` at repo root, plus `LICENSES/Apache-2.0.txt`.
- **Documentation: basics + interface** ✅ — `README.md` + `docs/`.
- **English** ✅.
- **Maintained / not unsupported** ✅ — active commit history, `CHANGELOG.md`.

### Change control

- **Public version-controlled source repo** ✅ — GitHub, public.
- **Unique version numbering (SemVer)** ✅ — `CHANGELOG.md` + tagged releases (`vX.Y.Z`).
- **Release notes for each release** ✅ — `CHANGELOG.md`; the release workflow also builds notes per tag.

### Reporting

- **Bug-reporting process documented** ✅ — `.github/ISSUE_TEMPLATE/bug_report.yml`, `CONTRIBUTING.md`.
- **Vulnerability reporting process** ✅ — `SECURITY.md` ("Reporting issues").
- **Private vulnerability reporting channel** ⚠️ — enable **Private vulnerability reporting** in Settings → Code security (one click), and reference it in `SECURITY.md`.

### Quality

- **Working build system** ✅ — frontend `npm run build`, backend PyInstaller runtime, Tauri release workflow.
- **Automated test suite** ✅ — `backend/tests/` (`pytest`), run in CI (`ci.yml`).
- **Tests added for new functionality (policy)** ✅ — `CONTRIBUTING.md` states the expectation; this project adds pure tests alongside features.
- **Continuous integration** ✅ — `.github/workflows/ci.yml` runs tests, typecheck, build, lint on every PR/push.
- **Warning flags / linters enabled** ✅ — `ruff` (backend) + `tsc` typecheck (frontend) in CI.

### Security

- **Developer knowledge of secure design** ✅ — `SECURITY.md` documents the local-first safety boundaries (no shell from frontend, no auto-execution, etc.).
- **Good cryptographic practices** ✅ — release artifacts are signed (Tauri updater signing keys); no home-grown crypto.
- **Delivery over HTTPS / signed** ✅ — releases via GitHub HTTPS; `SHA256SUMS.txt` published per release; updater artifacts signed.
- **Publicly known vulnerabilities fixed** ✅ — Dependabot (`.github/dependabot.yml`) + CodeQL + Scorecard.

### Analysis

- **Static analysis** ✅ — CodeQL (`codeql.yml`) + `ruff`.
- **Dynamic analysis** — the only passing-level blocker is the one **MUST**
  criterion (`dynamic_analysis_fixed`); the other three are SUGGESTED and don't
  block. Recommended answers on bestpractices.dev/projects/13357:
  - `dynamic_analysis` → **Met**: the pytest suite runs the software in CI on
    every push, exercising real runtime behavior; CodeQL provides SAST.
  - `dynamic_analysis_unsafe` → **N/A**: the produced software is Python +
    TypeScript; the only Rust is the memory-safe Tauri shell — no C/C++.
  - `dynamic_analysis_enable_assertions` → **Met**: tests run under CPython with
    assertions enabled (no `-O` / `PYTHONOPTIMIZE`); pytest evaluates `assert`.
  - `dynamic_analysis_fixed` (**MUST**) → **Met**: no separate dynamic-analysis
    tool is used, so there are no such findings; any confirmed medium+ severity
    exploitable vulnerability would be fixed promptly.

### Remaining one-time actions for a clean Passing

- ⚠️ Enable **Code scanning** (for Scorecard + CodeQL SARIF).
- ⚠️ Enable **Private vulnerability reporting** and link it from `SECURITY.md`.
- ⚠️ (Recommended) Add **branch protection** on `main`: require PR + 1 review — lifts Scorecard's Branch-Protection / Code-Review checks and the Best Practices change-control answers.

Everything else on the passing checklist is already backed by files in this repo.
