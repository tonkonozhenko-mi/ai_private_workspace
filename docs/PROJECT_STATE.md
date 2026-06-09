# Project State

## Project

**Name:** AI Private Workspace  
**Current state snapshot:** June 8, 2026

AI Private Workspace is a local-first AI workspace for project
onboarding, DevOps, developer, documentation, support, and manager assistants.
It combines deterministic project inspection, local RAG, safe command approval,
and local model experimentation foundations while keeping private project data
under the user's control.

This document is the primary handoff reference for continuing work after a chat
session, context window, or contributor change.

## Architecture Summary

The current application is a Python 3.11+ FastAPI backend organized using Clean
Architecture and Ports and Adapters.

- `backend/app/core/domain`: framework-neutral domain models, registries,
  deterministic rules, analyzers, prompts, and policies.
- `backend/app/core/use_cases`: application orchestration through ports.
- `backend/app/core/ports`: interfaces for persistence, filesystem access,
  model catalog loading, vector storage, embeddings, LLMs, command execution,
  and runtime health.
- `backend/app/adapters`: SQLite, in-memory repositories, local filesystem,
  Qdrant, Ollama, command runners, runtime health checkers, and user model
  catalog loading.
- `backend/app/api/routes`: thin FastAPI HTTP routes.
- `backend/app/api/schemas`: Pydantic request/response models and domain
  conversion helpers.
- `backend/app/api/dependencies.py`: composition root selecting configured
  adapters and shared in-memory services.
- SQLite: default persistence for workspace state, scans, index status,
  commands, and timeline events.
- Qdrant: optional persistent vector-store adapter.
- Ollama embeddings: optional local embedding-provider adapter.
- Ollama LLM: optional local answer-generation adapter.

Core code must remain independent from FastAPI, SQLite, concrete adapters,
Qdrant clients, Ollama clients, and subprocess execution.

See [ARCHITECTURE.md](ARCHITECTURE.md), [API_INVENTORY.md](API_INVENTORY.md),
[FRONTEND_API_MAP.md](FRONTEND_API_MAP.md), and
[CONFIGURATION.md](CONFIGURATION.md) for detailed references.

## Current Major Capabilities

### Workspace And Onboarding

- Workspace creation, retrieval, listing, metadata updates, archive, and restore.
- Lightweight workspaces overview for the app home screen.
- Workspace summary, dashboard, readiness, and Quick Start read models.
- Runtime health and deterministic runtime setup guide.
- Assistant profiles and workspace assistant recommendations.
- Onboarding plan, setup-command instructions, and bootstrap workspace flow.

### Project Understanding

- Deterministic local project scanning.
- Data-driven Skill Registry.
- Terraform, Terragrunt, GitLab CI, and GitHub Actions analyzers.
- Deterministic analysis summary and project overview report.

### Command Safety

- Deterministic command suggestions.
- Persistent command proposal, approval, rejection, and audit workflow.
- Command risk classification and conservative execution policy.
- Fake command runner by default.
- Optional guarded local command runner using `shell=False`, policy approval,
  timeouts, output limits, and workspace-root restrictions.

### Local RAG

- Deterministic file chunking and workspace indexing.
- Persistent index-status metadata.
- In-memory vector store by default and optional Qdrant adapter.
- Fake embeddings by default and optional Ollama embeddings.
- Context search.
- Workspace question answering through fake or optional Ollama LLM providers.
- Source-grounded RAG prompts, no-context diagnostics, and deterministic answer
  quality warnings.

### Activity And Continuation

- Persistent workspace timeline.
- Timeline backfill for workspaces created before timeline support.
- Recent activity included in workspace read models.

### Model Management And Experiments

- Static local model catalog and optional reloadable user JSON catalog through
  `USER_MODEL_CATALOG_PATH` and `POST /models/catalog/reload`.
- Deterministic model recommendations by assistant profile, laptop profile,
  task, model type, and workspace performance history.
- Workspace-aware recommendation explanations and switching plans.
- Persistent model experiment runs, comparison summaries, and manual candidate
  ratings.
- Workspace model selection state for LLM and embedding preferences.
- Read-only selection status, usage plan, embedding indexing plan, models
  dashboard, and dashboard summary.
- `POST /workspaces/{workspace_id}/ask-selected` for asking with the persisted
  selected LLM without changing runtime configuration.

### Frontend Workspace

- Vite, React, and TypeScript frontend in `frontend/`.
- Dark workspace sidebar with workspace status, assistant mode, index state,
  skill count, and next action.
- Overview, Ask, Models, Actions, and Activity tabs.
- Overview cards for project status, index status, quick start, activity, local
  model status, and primary next action.
- Ask tab with manual submit, example questions, non-blocking project-question
  guidance, local session history, answer diagnostics, quality warnings, and
  source inspection.
- Models tab with selected/active runtime, readiness, recommendations,
  performance history, and copy-only local activation guide.
- Actions tab with read-only UI action catalog and endpoint inspection.
- Activity tab backed by persistent timeline data.
- Unified status badges, loading/error/empty states, polished layout, safe text
  wrapping, and responsive behavior.

## Current Runtime Modes

### Default Development Mode

- SQLite workspace persistence.
- In-memory vector store.
- Fake deterministic embeddings.
- Fake deterministic LLM.
- Fake command runner.

This mode is self-contained and used by the normal test suite.

### Real Local Mode

- Qdrant for persistent vector context.
- Ollama for local embeddings.
- Ollama for local LLM generation.
- Fake command runner remains the safe default.

The verified runtime target is:

- `VECTOR_STORE=qdrant`
- `EMBEDDING_PROVIDER=ollama`
- `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`
- `LLM_PROVIDER=ollama`
- `OLLAMA_LLM_MODEL=llama3.2`

This real local AI happy path has been manually verified end to end: runtime
health reported Qdrant and Ollama as configured and healthy, the workspace was
reindexed into Qdrant, model selection status became `ready`, `ask-selected`
returned an Ollama answer with relevant sources, the frontend Overview showed
Local AI status `Ready`, Ask showed `ollama/llama3.2`, and Activity recorded
Ollama-backed workspace question events.

Qdrant and Ollama remain optional. No cloud API is required for the current
backend MVP. See [CONFIGURATION.md](CONFIGURATION.md#real-local-ai-runtime)
for exact startup, verification, and troubleshooting commands.

## Safety Principles

- Commands are never executed without explicit proposal approval and a
  policy-allowed decision.
- Destructive and compound-shell commands are blocked from automatic execution.
- Write and unknown-risk commands remain manual-only.
- Setup commands and onboarding commands are instructions only.
- Real command execution is disabled by default.
- No model downloads happen automatically.
- No active runtime settings are changed automatically.
- No cloud APIs are used by default.
- Project data and model workflows are designed to remain local-first.

## Latest Completed Task

**Frontend Polish And Real Local AI Happy Path**

The frontend MVP has been expanded and polished into a usable local workspace:
workspace sidebar, Overview, Ask, Models, Actions, and Activity tabs are in
place with consistent badges, shared state components, safe copy-only setup
instructions, local Ask session history, source inspection, and responsive
visual cleanup.

The real local AI happy path has also been verified with Qdrant, Ollama
embeddings, Ollama LLM generation, workspace reindexing, selected model
readiness, real `ask-selected` answers, source-grounded responses, and frontend
confirmation.

## Recommended Next Task

**Documented Runtime And Model Selection UX**

The immediate follow-up is to keep the verified real local runtime documented
and then improve the frontend model-selection editing flow. Future UI work
should continue to be explicit and safe: copy commands or explain actions, but
do not start runtimes, download models, reindex, or execute commands without a
separate deliberate design.

See [NEXT_STEPS.md](NEXT_STEPS.md) for the expected behavior and safety rules.

## Native UX Design Direction

A new Apple-style design-system foundation has been started for Phase 8. The
frontend now has shared CSS tokens for typography, spacing, radius, color,
shadows, focus rings, sidebar surfaces, and semantic states. This is intended
to move the UI from a developer-dashboard feel toward a calmer native workspace
experience while preserving the current safe behavior and local-first runtime
model.

The next UX work should avoid a full rewrite. Continue with small visual and
interaction tasks: app shell refinement, Models tab simplification, Ask tab
conversation layout, and progressive disclosure for advanced runtime and
experiment details.

## Task 106 App Shell Refinement

Phase 8 continued with an app-shell refinement. The workspace tabs now use a
segmented-control style inside a translucent navigation shell, the current
workspace is shown as contextual chrome, and the sidebar/workspace cards were
softened to feel less like a dense developer dashboard. The Overview header was
also restyled as a calmer workspace hero surface.

This task was visual-only. It did not change backend behavior, API calls,
workspace selection logic, model selection, Ask, scan/index/reindex, or
experiment flows.

## Frontend UX roadmap update — Task 107

Phase 8 native-feeling UX work continued with a Models tab simplification pass. The Models tab now has a guided hero, workflow steps, a compact insights grid, and a collapsible advanced activation guide. This is a layout/progressive-disclosure change only; existing model selection, Ask, experiment planning, experiment run, ratings, and history behavior remain unchanged.

## Frontend UX roadmap update — Task 108

Phase 8 continued with an Ask tab conversational redesign. The Ask screen is now positioned as a local workspace conversation: a guided composer, local-only safety copy, native answer card, source verification panel, and calmer verification notes. Existing behavior remains unchanged: Ask is still manual-submit only, sources/diagnostics/session history are preserved, and scan/index/reindex instructions remain copy-only.

### Ask source progressive disclosure

The Ask screen now keeps verification context visible without overwhelming the conversation: top sources appear first, previews are individually expandable, and additional sources are hidden behind an explicit Show all sources control.

## Frontend Task 110 — Actions Tab Native Simplification

Phase 8 Apple-style UX work continued with a native-feeling Actions tab pass.
The UI action catalog now reads less like an API table and more like a workspace
control inspector: grouped action cards, safety-first inspector copy, and raw API
details hidden behind progressive disclosure. No API behavior changed.

## Frontend Task 111 — Activity Native Timeline Redesign

Phase 8 Apple-style UX work continued with a native-feeling Activity tab pass.
The backend timeline is still read-only, but the UI now groups events by day,
shows compact activity summaries, uses calmer human-readable labels, and hides
raw metadata behind an explicit details disclosure. This keeps the Activity tab
useful for audits and demos without feeling like a low-level event log.

No behavior changed: the Activity tab does not replay events, execute commands,
run scan/index/reindex, mutate workspace state, or change runtime settings.

## Frontend Task 112 — Overview Product Status Section

Phase 8 Apple-style UX work continued with a Product Status section on the
Overview tab. The section summarizes workspace readiness across Local AI,
indexed context, model learning/experiment feedback, and safety posture. It is
intended for demos and day-to-day orientation so users can quickly see whether a
workspace is ready for Ask, whether indexed context exists, and what the next
recommended action is.

This change is read-only and uses data already loaded for the Overview screen.
No backend behavior changed, no API calls were added, and the frontend still does
not execute shell commands, run scan/index/reindex automatically, call models, or
change runtime settings from this section.


### Phase 8 UX Cleanup

The native-feeling UX pass now includes final wording and visual cleanup. Action
mutation labels are less alarming, Ask source previews are compact, and advanced
API details stay hidden until explicitly expanded.

## Frontend Task 114 — UX Wording Simplification

Phase 9 beginner-friendly UX work has started with a wording pass. The frontend
now prefers user-facing labels such as chosen AI model, chosen search model,
context ready, technologies found, rebuild search context, and workspace
capabilities instead of more internal terms like selected LLM, embedding,
index/reindex, or API catalog. The goal is to preserve technical accuracy while
making the app easier to understand for users who are not already familiar with
LLM/RAG terminology.

This was a wording and UI-copy change only. No backend behavior, API calls,
model calls, runtime settings, scan/index execution, or experiment behavior was
changed.

## Frontend UX update — Task 115

Overview now uses one clearer primary CTA for the first workspace question. This keeps the main dashboard more beginner-friendly and reduces repeated advisory messaging while preserving all existing read-only data and safety behavior.

## Task 116 — Capabilities Tab Wording

The frontend now labels the former Actions tab as Capabilities. The route/internal tab id remains `actions` and the backend endpoint remains `/ui-actions`; this is a user-facing wording change only. The screen remains inspection-only and does not execute capabilities from the catalog. Technical endpoint details are still available behind an explicit disclosure.

## Frontend Task 117 — Activity Wording Simplification

Phase 9 beginner-friendly UX work continued with a wording pass for the Activity tab.
Technical event labels were softened so the timeline reads like a user-facing activity
history rather than a backend event log. Examples include `LLM provider` becoming
`AI provider`, `LLM model` becoming `AI model`, and `quality_warnings_count`
becoming `Verification notes`.

No behavior changed: the Activity tab remains read-only and does not replay events,
run commands, rebuild context, change runtime settings, or update model selection.

## Frontend Task 118 — Models Simple / Advanced Split

Phase 9 beginner-friendly UX work continued by separating the Models tab into a
simple model view and a collapsed advanced runtime section. The simple view now
explains the two concepts most users need first: the AI answer model and the
search context model. Backend defaults, selected-vs-runtime details, and rebuild
context diagnostics remain available under Advanced details for troubleshooting.
No backend endpoints, payloads, or execution behavior changed.

## Frontend Task 119 — Models Selection Editor Simplification

Phase 9 beginner-friendly UX work continued by making the Models selection editor secondary. The main Models tab now leads with the simple AI answer model and search context model cards, while the manual model-changing controls are hidden behind an optional disclosure titled "Change workspace models".

This reduces cognitive load for new users and keeps advanced controls available for users who intentionally want to change workspace model preferences. No backend endpoints, payloads, runtime settings, model calls, scan/index/rebuild behavior, or command execution changed.


## Task 120 — Models experiments simplification

- Simplified the Models experiment area into an optional model comparison disclosure.
- Renamed experiment-oriented wording to user-facing comparison wording.
- Replaced Candidate A/B with Model A/B and warnings with verification notes where visible.
- Kept model comparison explicit and manual; no backend changes, no new API calls, no automatic model switch, and no automatic search-context rebuild.

## Task 121: Models Lower Dashboard Wording Polish

The Models tab lower summary cards were polished to remove remaining technical
LLM wording from the user-facing UI. Readiness, recommendations, and history now
use product-oriented labels while preserving all existing backend contracts and
manual-submit safety behavior.


## Task 122 — Guided Onboarding and Models Polish

Added a beginner-friendly guided path on the Overview screen so users can understand the workspace journey: scan project, build search context, ask a question, and compare models later. The guide uses existing dashboard/model summary data and only navigates between existing frontend tabs. It does not run scan, index, rebuild, model calls, commands, or backend mutations automatically.

The Models tab also received a small polish pass: advanced model details are framed as technical details, advisory step cards use less workflow-like wording, and recommendation/history panels explain fit score and past results more clearly. No backend contracts or API calls changed.


## Task 123 — Final Beginner UX / Apple-Style Cleanup

Phase 9 received a final product polish pass focused on first-time comprehension and lower visual noise. Overview guided-path copy is shorter, setup safety is presented as a small note, Models uses a lighter product framing, repeated ready/status badges were reduced in technical disclosure areas, and remaining helper text was simplified.

This is a frontend presentation-only change. It does not add API calls, run scan/index/rebuild, execute shell commands, call models automatically, change backend defaults, or mutate runtime settings.

## Task 124 — Settings Page Foundation

Phase 10 settings and personalization work has started with a read-only Settings tab. The first version introduces the product structure for future preferences without saving settings yet. It shows local backend connection details, appearance placeholders, Ask defaults, AI model defaults, and the local-only safety posture.

This is a frontend presentation-only foundation. It does not add backend endpoints, persist settings, execute commands, rebuild search context, restart the backend, or change model/runtime behavior.

## Task 125 Update — Browser-Local Settings Preferences

The Settings screen now includes safe browser-local preferences stored in
`localStorage` only. Users can choose theme, interface density, default Ask
source snippets, and preferred workspace landing tab without changing backend
state.

Safety constraints remain unchanged: these preferences do not execute shell
commands, scan or index projects, rebuild search context, restart the backend,
or change local model runtime. Ask uses the saved default source snippet count
when a workspace Ask session opens.

## Task 126 — Dark Theme Token Repair

The dark theme palette was repaired so dark mode uses a dedicated Apple-style dark token set instead of partially inheriting light surfaces. Core surfaces, raised cards, navigation, guided onboarding cards, product status cards, model cards, status badges, form controls, and key text colors now have explicit dark-mode contrast rules.

This is a frontend style-only fix. It does not change settings persistence, backend APIs, scan/index/rebuild behavior, model runtime, command execution, or workspace data.

## Task 127: Remaining Dark Surface Fixes

Task 127 completes the dark-mode repair pass for the remaining component-specific
surfaces. Ask, Capabilities, and Activity now use dark surfaces instead of
hard-coded light cards. The task also formats capability titles, descriptions,
and reasons so backend-facing `LLM` wording does not leak into the user-facing
Capabilities screen.

No backend APIs, runtime behavior, scan/index/rebuild behavior, model selection,
or shell execution behavior changed.


## Task 128 — Settings reset and preference clarity

- Added browser-local save feedback for Settings preferences.
- Added a two-step reset flow for local UI preferences only.
- Reset affects theme, density, landing tab, and default source snippets in localStorage.
- No backend API, command execution, scan, index, rebuild, or model/runtime change is introduced.

## Task 129 — Settings export/import local preferences

Settings now includes a browser-local export/import section for UI preferences. Users can copy the current preferences as JSON, load the current JSON into an import box, validate pasted JSON, and import supported values into localStorage-backed preferences.

The import flow only accepts supported theme, density, default source snippet, and landing tab values. It does not call backend APIs, access the file system, execute shell commands, scan or index projects, rebuild search context, restart services, or change model/runtime configuration.

## Task 130 — Settings backend connection preference

Settings now allows the local backend URL to be edited and saved as a browser-local preference. The frontend API client reads the saved connection target for future API calls, and the sidebar/settings views show the current target.

This remains frontend-only configuration. It does not add backend endpoints, execute shell commands, scan or index projects, rebuild search context, restart services, or change model/runtime settings.

## Task 131 — Settings backup section simplification

- Simplified the Settings backup area into an optional `Backup local settings` disclosure.
- JSON export/import tools are hidden by default to keep Settings lightweight for normal users.
- Updated backend connection save wording to be less technical.
- Reduced the visual weight of the reset preference button while keeping the two-step confirmation.
- No backend APIs, shell execution, scan/index/rebuild, or model/runtime behavior changed.

## Task 132 — Phase 10 final polish

Phase 10 settings work received a final polish pass. The Settings AI defaults
section now includes a safe `Open Models` navigation action so users know where
to review, compare, or change workspace model choices. The backend connection
copy was tightened to explain when the URL should be changed and reminds users
to refresh workspace data after changing the browser-local API address.

This remains frontend-only UI polish. It does not introduce backend endpoints,
execute commands, scan or index projects, rebuild search context, restart
services, or change model/runtime settings.

## Task 133 — Workspace Creation / Onboarding UI Foundation

Phase 11 real workspace onboarding has started with a dedicated frontend create-workspace flow. The sidebar now has an `Add project` action and the main content can show a guided onboarding form for a workspace name, local project path, assistant mode, and privacy mode.

The form calls the existing `POST /workspaces` backend endpoint only after explicit user submission. Creating a workspace stores workspace metadata in the local backend and then selects the new workspace so the user can continue with the guided path: scan project, build search context, ask questions, and compare models later.

Safety constraints remain unchanged: the frontend does not execute shell commands, scan files, build/rebuild search context, call models, change runtime settings, or run setup automatically from the create flow.

## 2026-06-09 — Task 134: Branding rename, safe assistant mode IDs, and GitHub CI

The product-facing name is now **AI Private Workspace**. The frontend sidebar, Settings copy, package metadata, and docs were updated away from the old Workbench naming.

Workspace creation now uses backend-supported assistant profile IDs. The user-facing **Support mode** option sends `support_incident`, which matches the backend assistant profile list and avoids the previous `Unknown assistant profile: support` dashboard error.

Settings now includes browser-local branding controls for logo initials and accent color presets. These preferences only affect the local UI and are stored in localStorage; they do not call backend APIs or change runtime/model behavior.

GitHub CI was consolidated into `.github/workflows/ci.yml` with frontend typecheck/build and backend pytest jobs. The old generated template workflows were removed.

## Task 135 — Workspace archive UI

Workspace list management now includes a safe archive flow for old or broken workspaces. Each workspace card exposes a secondary `Archive` action with a two-step confirmation. Archiving calls the existing `POST /workspaces/{workspace_id}/archive` endpoint and refreshes the workspace overview afterward, so archived workspaces disappear from the active sidebar list.

This is a reversible workspace metadata lifecycle operation. The frontend does not hard-delete local files, execute shell commands, scan/index/rebuild context, call models, or change runtime settings.


## Task 136 - Archived workspace restore and create onboarding polish

Workspace management now includes a safe archived workspace view in the sidebar. Users can show archived projects, restore an archived workspace with one explicit click, and return it to the active workspace list without deleting local files or running any commands. The create workspace screen was also polished with a clearer Apple-style onboarding hero, lighter guidance, clearer field help, and selected-mode preview copy.

Safety remains unchanged: restore only calls the workspace lifecycle endpoint, and create still does not scan, index, rebuild context, execute shell commands, or call models automatically.

## Task 137 — Workspace setup flow, archive UX fix, and CI v2

Phase 11 onboarding now includes explicit setup actions on the Overview guided path. Unscanned workspaces can be scanned from the guided path with a user click, scanned but unindexed workspaces can build search context with a user click, and ready workspaces route the user to Ask. These calls use the existing local backend endpoints only after explicit user action:

- `POST /workspaces/{workspace_id}/scan`
- `POST /workspaces/{workspace_id}/index`

The sidebar archive view was clarified so active workspaces remain visually separate from archived workspaces. Showing archived workspaces should not remove the archive action from active workspace cards; archived cards only expose Restore.

GitHub CI was improved with workflow concurrency, cached frontend/backend dependency installs, clearer job names, and workflow summaries for frontend typecheck/build and backend pytest.

Safety remains unchanged: the frontend does not execute shell commands, does not automatically scan/index/rebuild, does not delete local files, and does not change model/runtime settings.


## Task 138 — Skills and assistant focus flow

- Added a Workspace skills panel to Overview that explains detected skills, the current assistant focus, and starter presets.
- Added an Ask assistant-focus hint so users understand how the selected mode shapes answers.
- Documented the next direction for a customizable skill library with presets such as DevOps, Developer, Documentation, Incident Support, and Manager Summary.
- No backend behavior, shell execution, automatic scan/index, or model/runtime changes were added.

## Task 139 — Skill library presets and custom instructions

Added a browser-local Skill Library layer for AI Private Workspace. The UI now includes safe skill presets for DevOps, Developer, Documentation, Incident Support, and Manager Summary. Each preset has a purpose, best-for guidance, example questions, recommended file patterns, enable/disable state, and editable custom instructions stored in localStorage.

This task does not change backend runtime, prompt execution, scan, index, or model behavior yet. It prepares the UX and preference model for a later backend integration where selected skills can be included in Ask prompts.

## Task 140 — Connect skill instructions to Ask prompt contract

Browser-local skill presets now participate in explicit Ask requests. The frontend sends enabled skill names and custom instructions to `/workspaces/{workspace_id}/ask-selected` as `skill_context`. The backend accepts this optional field, converts it into bounded prompt guidance, and adds it to the RAG prompt as answer guidance only.

Skill instructions are not treated as project evidence. The prompt explicitly keeps project claims grounded in retrieved context chunks and source paths. Skill context is limited to five enabled skills and sanitized/truncated before prompt construction.

Timeline metadata now records how many skill instructions were applied and which skill names were included. No shell execution, scan/index/rebuild, model/runtime switching, or automatic action behavior was added.

Backend validation: `pytest` passed with 372 tests and 3 skipped in the task workspace.


## Task 141 — Skills UX and UI consistency polish

- Skill Enable buttons now switch to Disable when active.
- Custom skill instructions use explicit Save instruction and Saved locally feedback instead of invisible auto-save.
- Button sizing and skill-card typography were normalized for a cleaner Apple-style interface.
- No backend changes, no new API calls, no prompt changes, and no automatic scan/index/model actions.

## Task 142 — Ask conversation redesign

Ask was redesigned as an Apple-style workspace conversation. The Ask screen now shows user questions as conversation bubbles, assistant answers as AI bubbles, and answer actions directly on each response. Users can copy an answer, edit a previous question back into the composer, or ask the same question again with the current workspace context and enabled skills.

Sources, verification notes, diagnostics, and rebuild-context guidance remain attached to the assistant answer instead of being separated from the conversation. The redesign does not change backend behavior: Ask still runs only after an explicit user submit, and the frontend does not execute shell commands, scan/index automatically, or change runtime/model settings.

## Task 143 — Centered Ask composer and conversation layout

Ask was refined from a two-column form/result layout into a centered workspace conversation. The question composer now stays below the conversation timeline, so users read answers and ask follow-up questions in one place. The left panel was reduced to compact assistant focus and active-skill context.

The composer keeps source-snippet selection and example questions close to the input, while user bubbles, assistant bubbles, sources, verification notes, diagnostics, copy, edit, and ask-again actions stay attached to the conversation. This is a frontend layout and UX change only: no backend behavior, API contract, shell execution, scan/index/rebuild, or model/runtime behavior changed.


## Task 144 — Ask chat layout polish and compact sources

- Compacted the Ask focus sidebar so the conversation stays centered.
- Kept the composer at the bottom of the Ask flow with more bottom spacing for sources.
- Collapsed retrieved sources by default behind a Show sources / Hide sources control.
- Preserved explicit Ask-only behavior; no backend, shell, scan, index, or model runtime changes.
