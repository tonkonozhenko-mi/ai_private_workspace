# Next Steps

## Latest Completed Tasks

The deterministic **Model Switching Plan** is implemented at
`POST /models/switching-plan`. It explains what would happen if a user selected
another LLM or embedding model before any settings, indexes, or runtimes are
changed.

The plan is advisory only. It does not edit environment variables,
restart services, download models, switch providers, or trigger indexing.

The deterministic **Model Experiment Plan** is implemented at
`POST /models/experiments/plan`. It validates a workspace, enriches LLM
candidates from the current catalog, reports index readiness and per-request
override support, and describes future comparison measurements without running
or persisting an experiment.

Per-request LLM override is implemented on
`POST /workspaces/{workspace_id}/ask` for supported `fake` and `ollama`
providers. It allows one selected model to answer using the existing workspace
context without changing active runtime settings or restarting the backend.

Persistent **Model Experiment Runs** are implemented at
`POST /models/experiments/run`. Each run retrieves workspace context once,
executes explicitly selected candidates against the same prompt, isolates
candidate failures, persists results, and records timeline activity.

The deterministic **Model Experiment Comparison Summary** is implemented at
`GET /models/experiments/{experiment_id}/comparison`. It reads a saved run and
returns candidate completion state, answer length, latency, source count,
quality-warning count, deterministic scores, warnings, and a recommended
candidate.

Manual **Model Experiment Candidate Ratings** are implemented at
`POST /models/experiments/{experiment_id}/ratings` and
`GET /models/experiments/{experiment_id}/ratings`. Users can append ratings,
preferences, tags, and comments without changing original experiment answers.
Comparison summaries expose rating counts, averages, and preferred votes.

The workspace-scoped **Model Performance Summary** is implemented at
`GET /workspaces/{workspace_id}/model-performance`. It aggregates saved
candidate outcomes and manual feedback into explainable historical statistics
and deterministic performance scores without calling a provider or mutating
history.

Workspace-aware, rating-aware **Model Recommendations** are implemented at
`POST /workspaces/{workspace_id}/models/recommend`. The endpoint combines
current catalog scoring with workspace performance history while keeping every
historical adjustment visible and leaving models without history eligible.
Fake/testing models remain visible but receive an explicit workspace-use
penalty so they are not promoted above similarly scored real local models.

Deterministic **Model Recommendation Explanations** are implemented at
`POST /workspaces/{workspace_id}/models/explain`. Explanations combine catalog
fit, workspace history, switching impact, risks, and suggested next actions
without checking providers or changing model selection.

Persistent **Workspace Model Selection State** is implemented at
`GET /workspaces/{workspace_id}/models/selection` and
`PUT /workspaces/{workspace_id}/models/selection`. It stores selected LLM and
embedding preferences separately, reports configuration-match notes, and warns
when an embedding preference change may require reindexing.

Read-only **Workspace Model Selection Status** is implemented at
`GET /workspaces/{workspace_id}/models/selection/status`. It compares selections
with active configured provider/model names and workspace index metadata, then
reports restart, reindex, readiness, and next-action guidance.

Read-only **Selected Model Usage Plan** is implemented at
`GET /workspaces/{workspace_id}/models/usage-plan`. It explains whether the
selected LLM can be used through `/ask` per-request override and whether the
selected embedding can safely index and search with the active vector space.
It returns ordered setup, restart, reindex, and ask actions without performing
any of them.

**Ask With Selected LLM** is implemented at
`POST /workspaces/{workspace_id}/ask-selected`. It resolves the persisted
selected LLM, validates per-request provider support, and delegates to the
existing RAG ask flow. It never changes the active runtime or embedding/index
configuration.

Read-only **Selected Embedding Indexing Plan** is implemented at
`GET /workspaces/{workspace_id}/models/embedding-indexing-plan`. It explains
whether the selected embedding matches the active runtime, whether indexing and
search can proceed, and whether restart, a new vector collection, and reindexing
are required. It performs none of those actions.

Read-only **Workspace Models Dashboard** is implemented at
`GET /workspaces/{workspace_id}/models/dashboard`. It aggregates selected
models, readiness/status, usage guidance, embedding-indexing guidance,
workspace-aware recommendations, performance history, and the primary next
model action for the future workspace Models UI.

Compact **Workspace Models Dashboard Summary** is implemented at
`GET /workspaces/{workspace_id}/models/dashboard/summary`. It projects the
detailed dashboard into a lightweight model status card with selected/active
models, top recommendation, warning count, readiness, and next action.

Read-only **Local AI Activation Guide** is implemented at
`GET /workspaces/{workspace_id}/local-ai/activation-guide`. It turns selected
workspace models, active configuration, and index metadata into explicit
Qdrant, Ollama, backend-restart, reindex, and ask-selected instructions without
executing or verifying any of them.

Read-only **Workspace UI Action Catalog** is implemented at
`GET /workspaces/{workspace_id}/ui-actions`. It gives the future frontend stable
button/card metadata, action status, target HTTP method and endpoint, mutation
flags, and one deterministic primary action without executing any action.

The **Frontend API Map** is documented in
[FRONTEND_API_MAP.md](FRONTEND_API_MAP.md). It maps app screens, cards, action
buttons, provider boundaries, mutations, and timeline effects to the current
backend surface.

The **Frontend Workspace MVP** now exists in `frontend/`. It uses Vite, React,
and TypeScript to render a polished local workspace with a dark workspace
sidebar plus Overview, Ask, Models, Actions, and Activity tabs. The frontend
uses the stable API map, keeps setup commands copy-only, and never executes
workspace actions.

The **Real Local AI Happy Path** has been manually verified end to end:

- Runtime health shows `VECTOR_STORE=qdrant`, `EMBEDDING_PROVIDER=ollama`, and
  `LLM_PROVIDER=ollama`.
- Qdrant and Ollama are configured and healthy.
- `nomic-embed-text` is used for embeddings.
- `llama3.2` is used for local generation.
- Workspace reindex into Qdrant succeeds.
- Workspace selected LLM and embedding status becomes `ready`.
- `ask-selected` returns a real Ollama answer with relevant `terragrunt.hcl` and
  `main.tf` sources.
- Frontend Overview shows Local AI status `Ready`, Ask shows `ollama/llama3.2`,
  and Activity records Ollama-backed question events.

## Latest Frontend Model Selection Editing Flow

The frontend Models tab now includes a safe model selection editing flow. Users
can update selected LLM and selected embedding preferences from the UI without
using curl. The flow remains advisory and explicit:

- Shows current selected and active LLM/embedding.
- Lets the user choose from current selection, active runtime, and available
  recommendations.
- Saves one selection at a time only after explicit button click.
- Uses the correct backend payload: `provider`, `model`, `model_type`, and
  optional `selected_reason`.
- Refreshes read-only workspace/model dashboard state after save.
- Does not restart the backend.
- Does not download models.
- Does not reindex automatically.
- Does not execute setup commands.

## Next Recommended Tasks

1. Add copy-only frontend reindex guidance when selected embedding and active
   runtime match but the workspace needs a fresh index.
2. Add optional model catalog browsing beyond the top workspace recommendations.
3. Add better source-ranking diagnostics for Ask results.
4. Run a `llama3.2` vs `qwen2.5-coder` comparison experiment against the same
   workspace context.
- Usage and embedding-indexing plans explain whether ask/search/indexing can
  proceed.
- The Local AI Activation Guide provides copy-only setup instructions.

## Implemented Switching Rules

### LLM Changes

Changing only the LLM provider or LLM model does **not** require reindexing.
Existing vector chunks and embeddings can still be retrieved, then passed to
the newly selected generation model.

A switching plan should still warn about:

- Model availability not being verified unless a later runtime validation step
  is explicitly requested.
- Different context-window or performance characteristics.
- Potential answer-quality changes.

### Embedding Model Changes

Changing the embedding provider or embedding model **does** require a new index.
Stored vectors were created in the previous model's vector space and cannot be
safely searched using embeddings from another model.

The current Qdrant adapter already uses embedding-provider, model, and dimension
information when deriving collection names. The switching plan explains that a
new collection and workspace reindex are required.

### Vector Database Changes

Changing the vector-store adapter or vector database may require reindexing or
migration because the newly selected store may not contain existing workspace
chunks.

Examples:

- Moving from the in-memory vector store to Qdrant requires indexing into
  Qdrant.
- Moving from Qdrant to memory requires rebuilding the active in-memory index.
- Changing Qdrant URL or collection base name may point to an empty store and
  require reindexing.

Vector-store switching itself remains a future planning capability.

## Expected Future Endpoints

### `POST /models/experiments`

Expected purpose:

- Create a user-approved model experiment definition.
- Record selected models, task, workspace, inputs, and evaluation intent.
- Avoid silently changing active workspace/runtime configuration.

### `GET /models/experiments/{id}`

Expected purpose:

- Read experiment status and results.
- Support later answer comparison, benchmark evidence, and model-selection
  decisions.

## Follow-On Tasks

1. Frontend model selection editing flow with explicit confirmation and
   copy-only restart/reindex guidance.
2. Frontend reindex guidance that copies the correct curl command but does not
   execute it automatically.
3. Better source-ranking diagnostics for Ask results, including low-score and
   irrelevant-source explanations.
4. Optional `qwen2.5-coder` comparison experiment against `llama3.2` using the
   existing experiment endpoints.
5. Runtime model validation against installed Ollama models.
6. Ollama-backed real experiment polish and AI-assisted experiment evaluator.
7. Hugging Face metadata importer.
8. Desktop launcher and installer.

## Safety Requirements

- Never change active runtime settings automatically.
- Never download models automatically.
- Never start or stop Ollama, Qdrant, or other runtimes automatically.
- Never reindex automatically.
- Future UI flows must show the plan and require explicit user confirmation
  before runtime changes, downloads, migrations, or reindexing.
- Keep provider-specific checks and actions behind adapters.
- Keep switching-plan logic deterministic and framework-neutral.

## Completed: Frontend reindex guidance

The Ask and Models screens now show copy-only reindex guidance when the workspace index is missing, sources are empty, or selected embedding search/index readiness requires manual attention. The frontend still does not execute reindexing automatically.

Follow-up ideas:
- Add a dedicated setup checklist screen that combines runtime health, model selection, and index state.
- Add source ranking diagnostics for low-score or off-topic retrieval.
- Add optional qwen2.5-coder comparison experiments after the local Ollama/Qdrant path is stable.

## Frontend scan-before-index guidance

The frontend now shows copy-only scan and index commands when a workspace has no usable index. This reflects the backend requirement that project scanning must happen before workspace indexing. The UI still does not execute scan or index automatically.


## Task 99: LLM Runtime Mismatch Guidance

Frontend Models now treats LLM selection mismatches as an informational per-request preference, while embedding runtime mismatches remain action-required because they affect search/index compatibility. Saving LLM or embedding preferences remains manual-submit only and does not restart runtime, reindex, or execute commands.

## Completed: Frontend model experiment plan UI

The Models tab now includes a safe LLM comparison planner that calls
`POST /models/experiments/plan` and displays candidate readiness, shared-context
strategy, required restart/reindex flags, recommended actions, and notes. It is
advisory only and does not call models or run experiments.

Recommended next tasks:
- Add an explicitly confirmed frontend experiment run flow using `POST /models/experiments/run`.
- Add a comparison results screen for `GET /models/experiments/{id}/comparison`.
- Add manual rating UI for model experiment candidates.

## Completed: Frontend model experiment run UI

The Models tab can now run an explicitly requested local LLM comparison with
`POST /models/experiments/run` after the user generates a comparison plan. The
UI shows the experiment id, status, candidate answer previews, latency, source
counts, warning counts, notes, and simple manual-review hints. The flow calls
local LLMs but does not execute shell commands, change selected models, restart
runtime, download models, scan, index, or rebuild workspace context.

Recommended next tasks:
- Add a saved experiment details view using `GET /models/experiments/{experiment_id}`.
- Add deterministic comparison scoring view using `GET /models/experiments/{experiment_id}/comparison`.
- Add manual rating UI for model experiment candidates.

## After Task 102: Experiment ratings

Completed:

- Frontend can display experiment run results.
- Frontend can save manual ratings for experiment candidates.
- Ratings include provider/model, score, preferred flag, tags, and comment.
- Saved ratings are shown under the completed experiment result.

Recommended next tasks:

1. Add a small "Apply preferred model" guidance flow that copies or calls the existing model selection endpoint only after explicit confirmation.
2. Add experiment history browsing from the Models tab using existing workspace experiment endpoints.
3. Improve performance summary cards using accumulated ratings and preferred votes.

## After Task 103: Experiment history

Completed:

- The Models tab can load recent workspace experiments from `GET /workspaces/{workspace_id}/model-experiments`.
- Users can select a previous experiment and review its saved run details.
- Existing rating UI can be reused for selected history experiments.
- History browsing is read-only and does not run models or change model selection.

Recommended next tasks:

1. Add a deterministic comparison details view using `GET /models/experiments/{experiment_id}/comparison` if available.
2. Add an explicit "apply preferred model" confirmation flow that uses the existing model selection endpoint.
3. Improve performance summary cards using accumulated ratings, preferred votes, and experiment history.

## After Task 104: Apply preferred experiment model

Completed:

- Preferred experiment ratings can now be used to update the workspace selected LLM from the Models tab.
- The flow requires explicit confirmation before calling the model selection endpoint.
- Applying a preferred model only updates workspace LLM preference metadata.
- It does not restart runtime, reindex, rerun experiments, change embeddings, download models, or execute shell commands.

Recommended next tasks:

1. Add a deterministic comparison details view using `GET /models/experiments/{experiment_id}/comparison` if available.
2. Improve performance summary cards using accumulated ratings, preferred votes, and experiment history.
3. Add a small roadmap/status page that summarizes completed phases and next product milestones.

## Task 105: Apple-style design system foundation

Completed:

- Added CSS design tokens for typography, spacing, radius, shadows, semantic colors, dark sidebar colors, and focus rings.
- Started migrating core UI surfaces, buttons, cards, focus states, and monospace elements to the shared token language.
- Added a native-feeling interaction layer with softer hover states, active button feedback, consistent focus rings, text selection styling, and reduced-motion support.

Recommended next tasks:

1. Redesign the app shell with a more native segmented navigation and calmer workspace header.
2. Simplify the Models tab through progressive disclosure: current setup, recommendations, experiments, and advanced setup.
3. Redesign Ask as a conversational composer with collapsible verification/source panels.

## Task 106: App shell redesign

Completed:

- Reworked the workspace navigation into a native-feeling segmented control.
- Added a sticky translucent workspace navigation shell with current workspace context.
- Softened the dark sidebar, brand mark, selected workspace cards, and hover states.
- Turned the Overview workspace header into a calmer hero surface with better status separation.
- Refined card spacing, radius, shadows, and responsive behavior without changing data flow.

Safety and behavior:

- No backend behavior changed.
- No API calls were added.
- Tab navigation remains local UI state only.
- Workspace selection behavior remains unchanged.
- The redesign is visual shell polish only.

Recommended next tasks:

1. Simplify the Models tab with progressive disclosure and smaller focused sections.
2. Redesign Ask as a conversation-first interface with collapsible verification details.
3. Add a lightweight roadmap/status view for product demos and milestone tracking.

## Task 107 — Models tab UX simplification

- Reframe the Models tab as a guided workspace rather than one long technical page.
- Add a native-feeling hero summary for model workflow intent.
- Add a compact workflow strip: current setup, preferences, experiments, advanced setup.
- Group readiness, recommendations, and performance into a secondary insight grid.
- Move local AI activation commands into a collapsible Advanced activation guide.
- Keep behavior unchanged: no new backend calls, no automatic scan/index/reindex, no runtime mutation.

## Task 108 — Ask tab conversational redesign

Planned/completed direction:

- Reframe Ask as a conversation-first workspace instead of a form plus result page.
- Keep the composer manual-submit only and local-first.
- Present answers as a native-feeling conversation card with a user-question surface and answer bubble.
- Make verification feel calmer: source previews become a source verification panel, and quality warnings become verification notes.
- Keep scan/index/reindex guidance copy-only and never automatic.
- Keep session history local to the browser tab.

Safety remains unchanged: Ask still only calls `/workspaces/{workspace_id}/ask-selected` after explicit submit. The frontend does not execute commands, mutate runtime settings, or rebuild indexes automatically.

### Task 109 — Ask source progressive disclosure

Ask source previews now use progressive disclosure: the strongest two sources are shown first, each preview can be expanded or collapsed, and the remaining retrieved sources are available through a Show all sources control. This keeps the conversational Ask screen readable while preserving full verification context.

## Task 110 — Actions Tab Native Simplification

The Actions tab has been redesigned as a calmer read-only workspace control
inspector. Actions are grouped by purpose, raw endpoint details are hidden under
an explicit API details disclosure, and the inspector emphasizes safety posture
before transport-level metadata.

No backend behavior changed. The frontend still does not execute catalog actions,
restart services, run scan/index automatically, or mutate workspace state from
this screen.

## Task 111 — Activity Tab Native Timeline Redesign

Planned/completed direction:

- Reframe Activity as a native-feeling workspace timeline rather than a raw event log.
- Group events by day so recent activity is easier to scan.
- Add small activity summary cards for questions, project events, and model/experiment activity.
- Use human-readable event labels and softer category indicators.
- Hide raw metadata behind an explicit Show details disclosure.
- Keep the timeline read-only: no event replay, no command execution, no scan/index/reindex, and no runtime mutation.

Recommended next tasks:

1. Add a small product roadmap/status view for demo storytelling.
2. Consider a global command palette/search for navigation only.
3. Continue Apple-style polish with empty-state illustrations or lighter visual hierarchy refinements.

## Task 112 — Overview Product Status Section

Planned/completed direction:

- Add a native-feeling Product Status section to the Overview tab for demo storytelling and quick workspace readiness checks.
- Summarize Local AI readiness, workspace context/index readiness, model learning/experiment feedback, and safety posture.
- Keep the section advisory and derived from already-loaded dashboard/model summary data.
- Do not add backend calls or new runtime behavior.
- Keep all technical setup and scan/index/reindex flows manual and explicit.

Safety remains unchanged: the Overview section is read-only. It does not execute commands, run scan/index/reindex, call models, change selected models, or mutate runtime settings.


## Task 113 Completed: Final UX Wording And Visual Cleanup

The frontend now uses calmer action mutation wording, distinguishing workspace
context updates from activity recording. Ask source preview controls were reduced
to compact Preview/Hide text controls, and raw technical details remain behind
progressive disclosure. This closes the first native-feeling UX pass across the
main tabs.

## Task 114 — UX Wording Simplification

Continue reducing internal jargon in visible UI copy. Prefer:

- Chosen AI model instead of Selected LLM.
- Backend default AI model instead of Active LLM.
- Chosen search model instead of Selected embedding.
- Search context / Context ready instead of Index / indexed where possible.
- Rebuild search context instead of Reindex in user-facing text.
- Technologies found instead of skills when describing scan results.
- Workspace capabilities instead of API/action catalog when introducing Actions.

Keep backend identifiers, API payload names, and internal TypeScript types stable
unless a real API change is intended.

## Task 115 — Overview CTA simplification

- Reduced repeated “Ask first workspace question” messaging on the Overview screen.
- Added a single primary “Go to Ask” call-to-action in the product readiness section.
- Kept Models status and next-action information as secondary context.
- No backend behavior, API calls, model calls, scan, index, or runtime behavior changed.

## Task 116 — Capabilities Tab Wording

The frontend now labels the former Actions tab as Capabilities. The route/internal tab id remains `actions` and the backend endpoint remains `/ui-actions`; this is a user-facing wording change only. The screen remains inspection-only and does not execute capabilities from the catalog. Technical endpoint details are still available behind an explicit disclosure.

## Task 117 — Activity Wording Simplification

Status: completed.

The Activity tab now uses more beginner-friendly labels for common model, question,
context, and feedback events. The goal is to make the timeline understandable as a
workspace history without exposing backend-oriented terms such as `LLM provider` or
`quality_warnings_count` in the primary UI.

Next recommended beginner-friendly UX tasks:
- simplify the Models tab further with a simple/advanced split;
- add a first-run guided onboarding panel for new users;
- review remaining technical terms in empty states and helper text.

## Task 118 — Models Simple / Advanced Split

Status: prepared.

The Models tab should now lead with a simple user-facing view:

- AI answer model.
- Search context model.
- Overall ready / needs attention status.

Advanced selected-vs-runtime model details remain available in a collapsible
Advanced details section. This keeps the technical troubleshooting data without
making it the first thing a new user has to understand.

Validation:

```bash
cd frontend
npm run typecheck
npm run build
```

## Task 119 — Models Selection Editor Simplification

Status: prepared.

The Models tab should keep the simple model overview as the primary experience and move the model-changing controls into an optional disclosure. The selection editor is now framed as "Change workspace models" with a note that most users do not need to open it.

This remains a manual-submit flow only:

- saving an AI answer model only updates workspace preferences;
- saving a search context model only updates workspace preferences;
- no backend restart, search-context rebuild, command execution, or automatic model switch is performed by the frontend.

Validation:

```bash
cd frontend
npm run typecheck
npm run build
```


## Completed — Task 120 Models experiments simplification

The Models screen now keeps comparison/experiment tools optional so most users first see only the models currently used by the workspace. Next UX work can focus on first-run onboarding and new workspace guidance.

## Task 121: Models Lower Dashboard Wording Polish

The Models lower dashboard now uses friendlier labels for beginner-facing status:
`Ready now`, `Recommended models`, `Past model results`, `Fit score`, and
`Ask with chosen AI model`. This is a copy-only polish pass and does not change
model selection, experiments, runtime configuration, indexing, or API behavior.


## Task 122 — Guided Onboarding and Models Polish

Added a beginner-friendly guided path on the Overview screen so users can understand the workspace journey: scan project, build search context, ask a question, and compare models later. The guide uses existing dashboard/model summary data and only navigates between existing frontend tabs. It does not run scan, index, rebuild, model calls, commands, or backend mutations automatically.

The Models tab also received a small polish pass: advanced model details are framed as technical details, advisory step cards use less workflow-like wording, and recommendation/history panels explain fit score and past results more clearly. No backend contracts or API calls changed.


## Task 123 — Final Beginner UX / Apple-Style Cleanup

Status: prepared.

Validate the final beginner UX polish locally:

```bash
cd frontend
npm run typecheck
npm run build
```

Visual check:

- Overview guided path should explain the next step without long technical text.
- Models should lead with simple model status and keep technical/configuration details secondary.
- Repeated Ready badges should feel less noisy.
- Disclosures should look lightweight and optional.

After this check, Phase 9 can be considered ready to close. The next planned phase is Settings and personalization.

## Completed — Task 124 Settings Page Foundation

The frontend now includes a Settings tab with a safe read-only foundation for future personalization. It organizes connection, appearance, Ask defaults, AI defaults, and safety posture into a calm product settings page.

Next settings work can decide which preferences should be stored in localStorage and which should belong to backend workspace/global settings.

Validation:

```bash
cd frontend
npm run typecheck
npm run build
```

## Task 125 Completed — Settings Local Preferences

Settings now supports local browser preferences for theme, density, default Ask
source snippets, and preferred workspace landing tab. Preferences are stored in
`localStorage` and are intentionally frontend-only.

Next recommended work: review whether any setting should become backend-backed
workspace metadata. Keep safety settings read-only and avoid adding controls
that would automatically run scan, index, rebuild, restart, or model-switch
flows.

## Completed — Task 126 Dark Theme Token Repair

Dark mode now has a dedicated contrast-safe palette for page background, panels, cards, navigation, badges, inputs, and onboarding/model surfaces. Validate visually in Dark and System modes, then run:

```bash
cd frontend
npm run typecheck
npm run build
```

Next recommended work: continue Settings and personalization only after confirming both Light and Dark themes remain readable.

## Task 127: Remaining Dark Surface Fixes

Completed a targeted dark-mode cleanup for Ask, Capabilities, and Activity
components. Remaining hard-coded light cards were replaced with dark-mode
surface overrides, and user-facing capability text now normalizes old `LLM`
phrasing to chosen AI model wording.

Next: run local frontend typecheck/build and visually verify Light, Dark, and
System theme modes across Overview, Ask, Models, Capabilities, Activity, and
Settings.


## Task 128 — Settings reset and preference clarity

- Added browser-local save feedback for Settings preferences.
- Added a two-step reset flow for local UI preferences only.
- Reset affects theme, density, landing tab, and default source snippets in localStorage.
- No backend API, command execution, scan, index, rebuild, or model/runtime change is introduced.

## Task 129 — Settings export/import local preferences

Completed a safe browser-local export/import flow for Settings preferences.

Validation:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- Copy preferences JSON from Settings.
- Load current preferences into the import box.
- Import valid JSON and confirm UI preferences update.
- Try invalid JSON and confirm it is rejected with a clear message.
- Verify no backend calls, command execution, scan/index/rebuild, or model/runtime changes are triggered.

## Task 130 Completed — Configurable Backend URL

Settings now supports a browser-local backend URL preference with validation, save, and reset-to-default controls. After changing it, use Refresh to reload workspaces from the selected local backend.

Validation:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- Change Backend URL to a valid `http://` or `https://` value.
- Confirm Settings and the sidebar show the saved target.
- Click Refresh and verify workspace loading uses the new target.
- Try an invalid URL and confirm it is rejected.
- Reset to default and confirm the default URL is restored.

No backend APIs, command execution, scan/index/rebuild, or model/runtime changes are introduced.

## After Task 131

Validate Settings in light and dark themes. Confirm that backup tools are hidden by default, can be shown on demand, and that reset remains a safe two-step local-only action.

## Task 132 — Phase 10 Final Polish

Completed the final Phase 10 Settings polish:

- Added an `Open Models` action in Settings AI defaults.
- Clarified backend URL helper copy.
- Kept Settings changes browser-local and explicit.

Phase 10 can now be considered complete for the MVP. The next recommended phase
is **Phase 11 — Real Workspace Onboarding Flow**, focused on creating a new
workspace from a local path, guiding scan/index setup, and improving empty/new
workspace states.

## Task 133 — Workspace Creation / Onboarding UI Foundation

Added the first Phase 11 onboarding UI for creating a real workspace from a local path.

Validation:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- Click `Add project` in the sidebar.
- Create a workspace with name, local path, assistant mode, and privacy mode.
- Confirm the new workspace appears in the sidebar and becomes selected.
- Confirm the next guided step remains manual scan/setup.
- Confirm the create flow does not run scan, index, rebuild search context, model calls, shell commands, or runtime changes.

Next recommended work: add a beginner-friendly workspace setup screen for newly created or unscanned workspaces, with clear copy-only/manual guidance for Scan project and Build search context.

## Task 134 Completed — Branding and CI foundation

- Renamed user-facing product copy to **AI Private Workspace**.
- Added safe Support mode mapping to the backend-supported `support_incident` assistant profile.
- Added browser-local branding preferences for logo initials and accent color presets.
- Added a consolidated GitHub Actions CI workflow for frontend typecheck/build and backend tests.

Next recommended Phase 11 work:

1. Add a new workspace setup guide after creation.
2. Add explicit scan/build-context guided actions.
3. Add skill/focus selection after scan.
4. Add file include/exclude preferences before indexing.

## Task 135 Completed — Workspace archive UI

Added a safe archive flow to the sidebar workspace list.

Validation:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- Open the sidebar workspace list.
- Click `Archive` on an old workspace.
- Confirm the first click only opens confirmation controls.
- Click `Confirm archive` and verify the workspace disappears from the active list.
- Verify the app selects another workspace when the selected workspace is archived.
- Verify no shell commands, scan/index/rebuild, model calls, or runtime changes are triggered.

Next recommended work: add an archived workspace management view with `Show archived` and `Restore workspace`, or continue with guided scan/build-context onboarding.


## Task 136 verification - Archived workspace restore and create onboarding polish

- Archive a workspace from the sidebar and confirm it leaves the active list.
- Use Show archived and confirm the archived workspace appears.
- Click Restore and confirm it returns to the active list and opens Overview.
- Verify restore does not scan, index, rebuild search context, execute shell commands, or call models.
- Review Add project in light and dark themes for the polished onboarding hero, field helper text, assistant mode cards, and first-run guide.

Next recommended work: build the guided scan/build-context screen for newly created workspaces.

## Task 137 verification — Workspace setup flow and CI v2

Validate locally:

```bash
cd frontend
npm run typecheck
npm run build
```

```bash
cd backend
pytest
```

Manual checks:

- Open an unscanned workspace and confirm Overview shows `Scan project`.
- Click `Scan project` and confirm the scan completes and detected technologies update.
- Confirm the next action becomes `Build search context`.
- Click `Build search context` and confirm context/chunk counts update.
- Confirm ready workspaces show `Go to Ask`.
- Toggle `Show archived` and confirm active workspace cards still show `Archive`.
- Confirm archived workspace cards show `Restore` only.
- Confirm frontend never runs shell commands and setup actions only call explicit backend APIs after a click.
- Push to GitHub and confirm CI runs frontend and backend jobs with concurrency enabled.

Next recommended work: add skill/focus selection after scan and file include/exclude preferences before indexing.


## After Task 138

Next recommended product tasks:

1. Build a skill library and preset editor.
2. Let users start from common presets and extend them with project-specific guidance, for example adding Jenkins pipeline expertise to DevOps focus.
3. Add file include/exclude preferences before indexing so users can control what becomes search context.
4. Keep skill changes explicit and local; do not execute commands or rebuild context automatically.

## After Task 139

Next recommended product tasks:

1. Connect browser-local skill instructions to the Ask prompt flow through an explicit backend contract.
2. Add file include/exclude preferences before building search context.
3. Add a first-successful-Ask onboarding state that explains sources, confidence, and next actions.
4. Consider backend persistence for workspace-level skill profiles after the local UI proves useful.

## After Task 140

Next recommended product tasks:

1. Add file include/exclude preferences before building search context so users control which folders and file types become searchable.
2. Add a first-successful-Ask onboarding state that explains sources, applied skills, and verification notes.
3. Add workspace-level backend persistence for skills after the browser-local flow is validated.
4. Add tests for frontend skill-context payload handling in a future frontend test setup.


## Task 141 — Skills UX and UI consistency polish

- Skill Enable buttons now switch to Disable when active.
- Custom skill instructions use explicit Save instruction and Saved locally feedback instead of invisible auto-save.
- Button sizing and skill-card typography were normalized for a cleaner Apple-style interface.
- No backend changes, no new API calls, no prompt changes, and no automatic scan/index/model actions.

## After Task 142

Next recommended product tasks:

1. Add file include/exclude preferences before building search context so users control which folders and file types become searchable.
2. Add a first-successful-Ask onboarding state explaining answer bubbles, copy, edit, sources, applied skills, and verification notes.
3. Consider persistent workspace conversation history after the browser-tab conversation proves useful.
4. Add frontend component tests for Ask conversation interactions once the frontend test setup is introduced.

## After Task 143

Next recommended product tasks:

1. Add file include/exclude preferences before building search context so users control which folders and file types become searchable.
2. Add first-successful-Ask onboarding that explains answer bubbles, copy, edit, sources, applied skills, and verification notes.
3. Consider persistent workspace conversation history after the browser-tab conversation flow is validated.
4. Add frontend component tests for Ask composer, copy answer, edit question, and ask-again interactions once the frontend test setup is introduced.


## 
- Task 145 — Ask sources consistency and final chat polish: fixed collapsed source panels so attached sources no longer show the empty-source fallback until the real source list is empty.

Task 144 — Ask chat layout polish and compact sources

- Compacted the Ask focus sidebar so the conversation stays centered.
- Kept the composer at the bottom of the Ask flow with more bottom spacing for sources.
- Collapsed retrieved sources by default behind a Show sources / Hide sources control.
- Preserved explicit Ask-only behavior; no backend, shell, scan, index, or model runtime changes.

## After Task 146

Start Phase 12 — File selection / indexing control.

Recommended next product task: let users review which files will become searchable before rebuilding context. The first step should introduce safe include/exclude guidance and a read-only preview before adding more advanced indexing controls.

## After Task 147

Next recommended Phase 12 tasks:

1. Connect file include/exclude preferences to the explicit scan/index request contract.
2. Add a read-only file preview so users can see which files would be included or skipped before rebuilding search context.
3. Explain why each file is included or excluded based on pattern matches.
4. Keep rebuilding search context explicit; do not run scan/index automatically after editing file rules.

## After Task 149

Next large backend/product step: introduce real background jobs for long-running scan/index/model-comparison workflows with job status and backend-side cancellation.
