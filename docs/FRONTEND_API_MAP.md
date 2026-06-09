# Frontend API Map

This document maps the current AI Private Workspace backend to the
future frontend. It is a product-oriented companion to
[API_INVENTORY.md](API_INVENTORY.md), which remains the complete endpoint
inventory.

The frontend should prefer aggregate read models for initial screen loads, use
the Workspace UI Action Catalog for button state, and invoke mutating or
provider-backed endpoints only after an explicit user action.

## 1. App Home / Workspace List

### Endpoints

| Endpoint | UI responsibility |
| --- | --- |
| `GET /workspaces/overview` | Load lightweight workspace cards for the app home screen. |
| `GET /assistant-profiles` | Populate assistant-profile choices during workspace creation. |
| `POST /onboarding/bootstrap-workspace` | Create a workspace after the user confirms onboarding choices and return its initial setup state. |

### Workspace Cards

Build each card from `GET /workspaces/overview`:

- Workspace name, project path, assistant mode, and privacy mode.
- Readiness and Quick Start status.
- Latest scan and index status.
- Pending command count.
- Last activity title and timestamp.
- Next action ID and title for the card's primary button.

The overview endpoint is intentionally lighter than loading a dashboard for
every workspace. Open the workspace dashboard only after the user selects a
card.

### Archived Workspaces

- The default overview excludes archived workspaces.
- Request `GET /workspaces/overview?include_archived=true` for an archived
  workspace view.
- Archived workspaces remain persisted and can be restored; archive is not
  hard delete.
- Keep archive/restore actions in a card menu or settings surface rather than
  presenting them as the primary workspace action.

### Create Workspace Flow

1. Load assistant choices with `GET /assistant-profiles`.
2. Collect project path, assistant profile, laptop profile, privacy mode, and
   container runtime.
3. Submit `POST /onboarding/bootstrap-workspace`.
4. Navigate to the newly created workspace dashboard.

Bootstrap creates the workspace and initial timeline event. It does not scan,
index, execute commands, or automatically activate local AI.

## 2. Workspace Dashboard

### Endpoints

| Endpoint | UI responsibility |
| --- | --- |
| `GET /workspaces/{workspace_id}/dashboard` | Load the main workspace read model. |
| `GET /workspaces/{workspace_id}/ui-actions` | Load deterministic button/card action metadata. |

### Dashboard Layout

Use the dashboard response for:

- Main workspace status and identity.
- Summary counters and detected skills.
- Readiness and Quick Start progress.
- Assistant recommendation.
- Recent timeline events.
- Runtime health summary.
- Compact `models_summary` card.

Use the UI Action Catalog for buttons instead of hardcoding route availability:

- Render `status=blocked` actions disabled with their `reason`.
- Visually emphasize `status=recommended` and `is_primary=true`.
- Treat `optional` actions as secondary.
- Use `method` and `endpoint` only after the user invokes the action.
- Use `mutates_data` to decide whether confirmation or refresh behavior is
  appropriate. Prefer human wording in the UI: Ask actions should be described
  as recording workspace activity, while scan/index actions can be described as
  updating workspace context.

The dashboard can perform lightweight runtime health checks when Qdrant or
Ollama is configured. The UI Action Catalog does not call runtime providers.

## 3. Models Screen

### Endpoints

| Endpoint | UI responsibility |
| --- | --- |
| `GET /workspaces/{workspace_id}/models/dashboard` | Load the complete Models screen. |
| `GET /workspaces/{workspace_id}/models/dashboard/summary` | Load a compact Models status card. |
| `GET /workspaces/{workspace_id}/models/selection` | Load persisted workspace model preferences. |
| `PUT /workspaces/{workspace_id}/models/selection` | Save one selected LLM or embedding model. |
| `GET /workspaces/{workspace_id}/models/selection/status` | Compare selected models with active runtime and index state. |
| `GET /workspaces/{workspace_id}/models/usage-plan` | Explain how selected models can currently be used. |
| `GET /workspaces/{workspace_id}/models/embedding-indexing-plan` | Explain selected embedding activation and reindex requirements. |
| `GET /workspaces/{workspace_id}/local-ai/activation-guide` | Show ordered local AI setup instructions and command alternatives. |

### Recommended Screen Structure

- **Selected models:** selected LLM and embedding cards with provider/model
  identity and selection reason.
- **Active runtime:** active provider/model identities and mismatch warnings.
- **Readiness:** whether selected LLM ask, embedding index, and embedding search
  are available.
- **Recommendations:** ranked workspace-aware LLM recommendations.
- **Performance:** historical experiment and rating signals.
- **Activation:** explicit Qdrant, Podman, Ollama, backend restart, reindex, and
  ask-selected instructions.

### Model State Rules

- Model selection is preference state only. Saving it never changes active
  runtime settings or downloads a model.
- A supported selected LLM can be used per request through
  `POST /workspaces/{workspace_id}/ask-selected`.
- A selected embedding cannot be applied per request. Indexing and search must
  use the active embedding provider/model and matching vector space.
- An embedding provider/model change requires runtime alignment and workspace
  reindexing.
- Show the selected embedding indexing plan whenever the selected embedding
  differs from active configuration or the workspace is not indexed.
- The activation guide returns instructions only. Its `command` is the primary
  instruction; `commands` may contain ordered alternatives, such as starting an
  existing Qdrant container or creating it if missing.

## 4. Ask / RAG Screen

### Endpoints

| Endpoint | UI responsibility |
| --- | --- |
| `POST /workspaces/{workspace_id}/ask` | Ask using active providers or an explicit per-request LLM override. |
| `POST /workspaces/{workspace_id}/ask-selected` | Ask using the persisted selected workspace LLM. |
| `GET /workspaces/{workspace_id}/context/search` | Inspect retrieved workspace context without generating an answer. |
| `POST /workspaces/{workspace_id}/index` | Build or rebuild workspace context. |
| `GET /workspaces/{workspace_id}/index/status` | Load persistent indexing status and counts. |

### Ask Screen Behavior

- Disable normal Ask until readiness says `can_ask=true`.
- Allow Ask With Selected LLM when the Models summary says
  `can_ask_with_selected_llm=true`.
- Display answer sources with source path, relevance score, and preview.
- Display `diagnostic_code` and `diagnostic_message` prominently when no
  context is returned.
- Display `quality_warnings` as verification guardrails, not proof that an
  answer is incorrect.
- Provide Context Search as a source-inspection tool before or after asking.

### Reindex Warnings

Show a reindex action when:

- The workspace has never been indexed.
- Index metadata reports failure.
- Selected embedding does not match active embedding configuration.
- The active vector store changed or points to an empty collection.
- The app uses the in-memory vector store and the API restarted.

The in-memory vector store loses chunks on restart even though persistent index
metadata may still say the workspace was indexed. In that case `/ask` returns a
diagnostic explaining that metadata exists but the active store has no chunks.
Qdrant is the persistent local vector-store option.

## 5. Experiments Screen

### Endpoints

| Endpoint | UI responsibility |
| --- | --- |
| `POST /models/experiments/plan` | Preview candidate readiness and experiment requirements. |
| `POST /models/experiments/run` | Run an explicitly confirmed shared-context model comparison. |
| `GET /models/experiments/{experiment_id}` | Load a saved experiment run and candidate results. |
| `GET /models/experiments/{experiment_id}/comparison` | Load deterministic comparison scores and recommended candidate. |
| `POST /models/experiments/{experiment_id}/ratings` | Save manual candidate feedback. |
| `GET /models/experiments/{experiment_id}/ratings` | Load manual ratings and comments. |
| `GET /workspaces/{workspace_id}/model-experiments` | List saved runs for a workspace. |
| `GET /workspaces/{workspace_id}/model-performance` | Load historical model performance for the workspace. |
| `POST /workspaces/{workspace_id}/models/recommend` | Load rating-aware workspace model recommendations. |
| `POST /workspaces/{workspace_id}/models/explain` | Explain why a model is or is not recommended. |

### Suggested Experiment Flow

1. Select a workspace question and candidate LLMs.
2. Preview with `POST /models/experiments/plan`.
3. Show warnings for unknown models, unsupported providers, installation needs,
   or missing workspace index.
4. Run only after explicit confirmation with `POST /models/experiments/run`.
5. Show candidate answers, sources, latency, and quality warnings.
6. Load the deterministic comparison summary.
7. Let the user rate candidates and mark preferred answers.
8. Reflect accumulated feedback in performance and workspace-aware
   recommendations.

The deterministic comparison score is not a semantic evaluator. Present it
alongside answers, sources, quality warnings, and manual feedback.

## 6. Commands Screen

### Endpoints

| Endpoint | UI responsibility |
| --- | --- |
| `GET /workspaces/{workspace_id}/commands/suggestions` | Load deterministic command templates. |
| `POST /workspaces/{workspace_id}/commands` | Create a pending command proposal. |
| `GET /workspaces/{workspace_id}/commands` | Load proposal and audit history. |
| `POST /commands/{command_id}/approve` | Approve a pending proposal. |
| `POST /commands/{command_id}/reject` | Reject a pending proposal. |
| `POST /commands/{command_id}/execute` | Execute an approved, policy-allowed proposal. |

### Approval Flow

1. Show suggestions as templates only; they are not proposals.
2. Require the user to explicitly create a proposal.
3. Display risk and policy decision before approval.
4. Allow approve or reject only while status is pending.
5. Enable Execute only when status is approved and policy mode is
   `auto_executable`.
6. Display stdout, stderr, exit code, status, and audit timestamps after
   execution.

Approval alone is not enough:

- Destructive commands are blocked.
- Compound shell commands are blocked.
- Write and unknown-risk commands are manual-only.
- Fake runner is the default.
- Local runner is opt-in, uses `shell=False`, and restricts `cwd` to the
  workspace project path.

## 7. Runtime / Setup Screen

### Endpoints

| Endpoint | UI responsibility |
| --- | --- |
| `GET /runtime/health` | Show reachability of configured local runtime components. |
| `POST /runtime/setup-guide` | Compare desired onboarding runtime with current health. |
| `POST /onboarding/setup-commands` | Return setup command instructions for Podman/Docker, Qdrant, Ollama, and backend startup. |
| `POST /onboarding/plan` | Build the deterministic onboarding plan for assistant, laptop, and privacy choices. |

### Runtime UI Rules

- Setup commands are instructions only and are never automatically proposed or
  executed.
- Health checks are lightweight and only check configured local dependencies.
- Qdrant and Ollama are optional; unavailable configured providers should
  produce degraded status rather than crash the app.
- Preserve local-only defaults and make any future non-local option explicit.
- Show Podman/Qdrant commands as alternatives: start an existing container
  first, create it only if it does not exist.
- Never imply that a model is installed unless a runtime check explicitly
  verifies it.

## 8. Suggested UI Navigation

### App-Level Navigation

- **Workspaces:** app home and workspace cards.
- **Create Workspace:** onboarding wizard.
- **Runtime:** runtime health and setup guidance.

### Workspace Tabs

| Tab | Primary backend surface |
| --- | --- |
| **Overview** | Workspace dashboard and UI Action Catalog |
| **Ask** | Ask, Ask Selected, Context Search, Index Status |
| **Models** | Models dashboard, selection, usage/indexing plans, activation guide |
| **Experiments** | Experiment runs, comparisons, ratings, performance |
| **Commands** | Suggestions, proposals, approvals, execution audit |
| **Timeline** | `GET /workspaces/{workspace_id}/timeline` |
| **Settings / Runtime** | Workspace metadata, archive/restore, runtime health/setup |

Use the UI Action Catalog to populate primary and secondary actions across
tabs. Navigation itself should remain stable even when an action is blocked;
show the blocked reason and route the user toward the recommended prerequisite.

## 9. State And Safety Rules

### Read-Only Endpoints

These endpoints read persisted metadata and do not call providers:

- Workspace overview, summary, readiness, Quick Start, and UI Action Catalog.
- Workspace model selection reads, selection status, usage plan, embedding
  indexing plan, Models dashboard, and Models dashboard summary.
- Local AI Activation Guide.
- Model catalog reads, recommendations, switching plan, experiment plan,
  comparison, performance summary, and recommendation explanation.
- Index status, saved scan retrieval, command list/suggestions, ratings list,
  experiment retrieval/list, and timeline retrieval.

Important exceptions:

- The main workspace dashboard is read-only but includes runtime health, which
  may perform lightweight Qdrant/Ollama checks when configured.
- Runtime health and runtime setup guide are read-only but may perform
  lightweight local provider health checks.
- Context Search is read-only but calls the active embedding and vector-store
  providers.
- Project Overview uses `GET` but records a timeline event and reads project
  files for deterministic analysis.

### Mutating Endpoints

Treat these as explicit user actions and refresh affected read models after
success:

- Workspace create/bootstrap, metadata update, archive, and restore.
- Workspace scan and index.
- Workspace model selection update.
- Ask and Ask Selected, because they record timeline events.
- Experiment run and experiment rating.
- Command proposal, approve, reject, and execute.
- Timeline backfill.
- User model catalog reload mutates only the in-memory catalog snapshot.

### Endpoints That Create Timeline Events

- Workspace create/bootstrap, metadata update, archive, and restore.
- Workspace scan and index.
- Project Overview generation.
- Ask and Ask Selected.
- Model experiment run and candidate rating.
- Workspace model selection update.
- Command proposal, approval, rejection, and execution.

### Endpoints That Never Call Providers

Planning, status, recommendation, explanation, selection, action-catalog, and
activation-guide endpoints are deterministic unless explicitly documented
otherwise. In particular, Models dashboards, UI Action Catalog, Local AI
Activation Guide, onboarding plan, onboarding setup commands, model experiment
plan, and command suggestions do not call Qdrant, Ollama, Hugging Face, LLMs,
or command runners.

### Explicit Provider And Execution Boundaries

These endpoints may call local providers only when explicitly invoked:

- `POST /workspaces/{workspace_id}/index`: filesystem, embedding provider, and
  vector store.
- `GET /workspaces/{workspace_id}/context/search`: embedding provider and
  vector store.
- `POST /workspaces/{workspace_id}/ask`: embedding/vector providers and
  selected or default LLM.
- `POST /workspaces/{workspace_id}/ask-selected`: active embedding/vector
  providers and persisted selected LLM.
- `POST /models/experiments/run`: active retrieval providers and explicitly
  selected candidate LLMs.
- `POST /commands/{command_id}/execute`: configured command runner, only after
  approval and policy checks.

No endpoint automatically downloads models, changes runtime configuration,
restarts the backend, starts containers, reindexes after model selection, or
executes setup commands.

## Frontend Integration Defaults

- Treat backend action IDs and statuses as stable product state.
- Use endpoint paths returned by `/ui-actions` for action buttons.
- Refresh the workspace dashboard and UI Action Catalog after a mutating action.
- Refresh Models dashboard data after changing model selection or saving model
  feedback.
- Refresh index status, readiness, and Ask controls after indexing.
- Preserve source paths, diagnostics, and quality warnings in the Ask UI.
- Require explicit confirmation before experiment runs and command execution.
- Never infer provider reachability from configured provider names alone.

### Implemented Model Selection Editing Flow

The current frontend Models tab includes a safe model-selection editor. It uses
only the existing workspace models dashboard data plus explicit user-submit
calls to:

- `PUT /workspaces/{workspace_id}/models/selection`

The editor saves one preference at a time with the backend payload shape:

```json
{
  "provider": "ollama",
  "model": "llama3.2",
  "model_type": "llm",
  "selected_reason": "Selected from the frontend Models tab."
}
```

For embeddings the same endpoint is used with `model_type: "embedding"`.
Saving a selection updates preference metadata only. The frontend does not
restart the backend, pull Ollama models, reindex the workspace, execute setup
commands, or change runtime environment variables. After a successful save, the
frontend reloads the read-only workspace/model dashboard state so readiness,
activation guidance, and next actions reflect the new selection.

## Reindex guidance UI

The frontend may display copy-only reindex guidance when Ask diagnostics report missing index context, when no sources are returned, or when the Models tab indicates that the selected embedding cannot be used for search/indexing yet.

This UI does **not** execute reindexing. It only shows a curl command the user can copy and run intentionally:

```bash
curl -X POST http://127.0.0.1:8000/workspaces/{workspace_id}/index
```

This preserves the local-first safety model: model selection is a manual preference update, while runtime restarts and reindexing remain explicit user actions.

### Scan-before-index guidance

When Ask or Models detects that a workspace has no usable index, the UI displays copy-only commands in the safe order:

1. `POST /workspaces/{workspace_id}/scan`
2. `POST /workspaces/{workspace_id}/index`

The frontend does not run these commands automatically.


## Task 99: LLM Runtime Mismatch Guidance

Frontend Models now treats LLM selection mismatches as an informational per-request preference, while embedding runtime mismatches remain action-required because they affect search/index compatibility. Saving LLM or embedding preferences remains manual-submit only and does not restart runtime, reindex, or execute commands.

## Task 100: Model Experiment Plan UI

The Models tab includes a safe, advisory LLM comparison planner. It calls only:

- `POST /models/experiments/plan`

The request uses the backend payload shape:

```json
{
  "workspace_id": "<workspace_id>",
  "question": "How is Terraform backend configured?",
  "candidates": [
    { "provider": "ollama", "model": "llama3.2", "model_type": "llm" },
    { "provider": "ollama", "model": "qwen2.5-coder", "model_type": "llm" }
  ]
}
```

The planner is read/advisory. It does not call candidate models, run experiments,
change selected models, restart runtime, download Ollama models, scan, index, or
mutate workspace data. Experiment execution remains a separate explicit flow.

## Task 101: Model Experiment Run UI

The Models tab includes an explicit local comparison run after a plan is generated. It calls only:

- `POST /models/experiments/run`

The run uses the same payload shape as the plan request:

```json
{
  "workspace_id": "<workspace_id>",
  "question": "How is Terraform backend configured?",
  "candidates": [
    { "provider": "ollama", "model": "llama3.2", "model_type": "llm" },
    { "provider": "ollama", "model": "qwen2.5-coder", "model_type": "llm" }
  ]
}
```

This flow calls local LLM candidates through the backend and may take time or use CPU/RAM. It still does not execute shell commands, change selected models, restart runtime, download models, scan, index, or rebuild workspace context. The UI displays experiment status, candidate answer previews, latency, source counts, warning counts, notes, and simple comparison hints. The hints are not an automatic winner; users should review answer quality and source grounding manually.

## Task 102 update: Experiment rating UI

The Models tab can save manual feedback for a completed model experiment.

Endpoints used:

- `GET /models/experiments/{experiment_id}/ratings` — loads saved ratings for a completed experiment.
- `POST /models/experiments/{experiment_id}/ratings` — saves a manual rating for one candidate.

Payload shape:

```json
{
  "provider": "ollama",
  "model": "llama3.2",
  "rating": 5,
  "is_preferred": true,
  "tags": ["better_source_grounding", "faster"],
  "comment": "Used both terragrunt.hcl and main.tf."
}
```

Safety notes:

- Rating does not change selected model preferences.
- Rating does not run an experiment.
- Rating does not reindex, restart the backend, or execute shell commands.

## Task 103: Model Experiment History UI

The Models tab can browse saved model experiments for the selected workspace.

Endpoint used:

- `GET /workspaces/{workspace_id}/model-experiments`

The history view shows recent experiment questions, status, shared source count,
candidate models, latency, warning counts, and source counts. Selecting a history
item opens the saved experiment result details and rating UI.

Safety notes:

- History browsing is read-only.
- Selecting a history item does not run models.
- Selecting a history item does not change selected models.
- Selecting a history item does not reindex, scan, restart runtime, or execute commands.

### Apply preferred experiment model

The Models tab can apply a preferred manual experiment rating as the workspace selected LLM after explicit user confirmation.

Endpoint used:

- `PUT /workspaces/{workspace_id}/models/selection`

Payload shape:

```json
{
  "provider": "ollama",
  "model": "llama3.2",
  "model_type": "llm",
  "selected_reason": "Selected from experiment <experiment_id> after manual preferred rating."
}
```

Safety behavior:

- The UI only shows this control for ratings marked as preferred.
- The user must confirm before the endpoint is called.
- Applying a preferred model does not restart the backend.
- Applying a preferred model does not reindex or change embedding settings.
- Applying a preferred model does not rerun the experiment or execute shell commands.
- After applying, the Models dashboard is refreshed so selected/default runtime status is visible.

## Design system note

Task 105 introduced a frontend design-system foundation in `frontend/src/styles.css`.
It is CSS-only and does not add API calls. Future frontend work should prefer
shared tokens for color, spacing, radius, focus rings, and surface styling before
adding new one-off CSS values.

## Task 106 App Shell Redesign Note

Task 106 refined the application shell and navigation styling:

- `App.tsx` wraps the workspace tabs in a native-feeling navigation shell and
  shows the current workspace context.
- `styles.css` adds segmented navigation, softer sidebar cards, a calmer
  workspace hero header, and responsive app-shell adjustments.

No API calls were added or changed. The shell redesign is visual and keeps tab
switching as local React state.

## Task 107 frontend layout note

The Models tab UX simplification does not add or change API calls. It only reorganizes existing data from the already-used models dashboard, activation guide, experiment plan/run, ratings, and history flows. Advanced local AI setup commands remain copy-only and are not executed by the frontend.

## Task 108 Ask UX note

The Ask tab was redesigned visually as a conversation-first workspace surface. API behavior did not change:

- Manual Ask still calls only `POST /workspaces/{workspace_id}/ask-selected`.
- Session history remains frontend state only.
- Scan/index/reindex guidance remains copy-only and is never executed by the frontend.
- Sources, diagnostics, quality warnings, and markdown answer rendering use the same response payload as before.

### Ask source disclosure

`AskWorkspace` continues to use `POST /workspaces/{workspace_id}/ask-selected`; source progressive disclosure is frontend-only and does not add API calls.

## Frontend Task 110 — Actions Tab Native Simplification

The Actions tab continues to consume only
`GET /workspaces/{workspace_id}/ui-actions`. The screen now presents actions as
purpose-grouped cards and shows the selected action in an inspector panel.
Endpoint and method details are available only in an advanced disclosure area
with copy support.

This change is visual only. The Actions tab remains read-only and does not invoke
any action endpoint.

## Task 111 Activity UX Notes

The Activity tab continues to use the existing read-only timeline data from
`GET /workspaces/{workspace_id}/timeline`. The frontend groups returned events
by local day, summarizes visible categories, and hides raw metadata behind a
local disclosure control. No new endpoints were added and no event action is
executed from this view.

## Task 112 Overview Product Status Notes

The Overview Product Status section is frontend-only and uses the existing
workspace dashboard and models summary data already loaded for the Overview tab.
It does not add new endpoints.

Displayed readiness signals:

- Local AI readiness from the models dashboard summary.
- Workspace context/index readiness from the workspace index status.
- Model learning signal based on recent model/experiment-related activity.
- Safety posture reminding users that frontend actions are explicit and do not
  execute shell commands.

No new API calls, mutations, scan/index/reindex actions, model calls, or runtime
changes were added.


### Final UX wording pass

The frontend avoids alarming mutation labels when the user-facing effect is only
activity recording. Raw API details remain available, but stay hidden behind
explicit disclosure controls. Source previews use compact Preview/Hide controls
so verification does not dominate the Ask screen.

## Task 114 UX Wording Notes

The frontend now presents model and context concepts with more user-friendly
labels while keeping the underlying API unchanged. UI labels may say "chosen AI
model" or "chosen search model", but the API still uses the existing model
selection and embedding fields. UI labels may say "rebuild search context", but
the backend endpoint remains `POST /workspaces/{workspace_id}/index`.

This keeps the interface easier to understand without changing contracts.

## Task 115 note

The Overview CTA simplification is UI-only. The new “Go to Ask” button switches the local frontend tab to Ask and does not call backend APIs directly.

## Task 116 — Capabilities Tab Wording

The frontend now labels the former Actions tab as Capabilities. The route/internal tab id remains `actions` and the backend endpoint remains `/ui-actions`; this is a user-facing wording change only. The screen remains inspection-only and does not execute capabilities from the catalog. Technical endpoint details are still available behind an explicit disclosure.

## Task 117 Activity Wording Notes

The Activity tab still reads from the same timeline endpoint and remains read-only.
Only user-facing labels changed. Backend event types and metadata keys are preserved,
but common labels are displayed in more user-friendly language, for example:

- `llm_provider` -> `AI provider`
- `llm_model` -> `AI model`
- `quality_warnings_count` -> `Verification notes`
- experiment rating events -> `Model feedback saved`
- index events -> `Search context rebuilt`

## Task 118 Models Simple / Advanced UX Notes

The frontend now presents model status in two layers:

- Simple view: AI answer model and search context model.
- Advanced details: chosen models, backend defaults, runtime mismatch details,
  and rebuild context guidance.

This is a presentation-only change. The Models tab still uses the existing model
selection, dashboard, recommendation, experiment, rating, and history APIs.

## Task 119 Models Selection Editor UX Notes

The model selection editor is now a progressive-disclosure section in the Models tab. It still uses the existing `PUT /workspaces/{workspace_id}/models/selection` flow through the existing frontend API client, but the UI presents it as optional model settings rather than a primary first-run task.

The frontend still does not restart the backend, rebuild search context, execute shell commands, or automatically switch runtime models after saving a workspace preference.


## Task 120 note — Model comparison UI

The frontend still uses the existing model experiment endpoints, but the user-facing UI presents this area as optional model comparison. The screen does not run comparisons until the user explicitly prepares and then runs the comparison.

## Task 121: Models Lower Dashboard Wording Polish

The Models tab lower dashboard now presents readiness, recommendation, and
history summaries with simpler user-facing labels. API endpoints, request
payloads, model experiment flows, and manual safety constraints are unchanged.


## Task 122 — Guided Onboarding and Models Polish

Added a beginner-friendly guided path on the Overview screen so users can understand the workspace journey: scan project, build search context, ask a question, and compare models later. The guide uses existing dashboard/model summary data and only navigates between existing frontend tabs. It does not run scan, index, rebuild, model calls, commands, or backend mutations automatically.

The Models tab also received a small polish pass: advanced model details are framed as technical details, advisory step cards use less workflow-like wording, and recommendation/history panels explain fit score and past results more clearly. No backend contracts or API calls changed.


## Task 123 note — final UX polish

Task 123 is a UI-copy and style polish pass only. It keeps all existing frontend API usage unchanged. Navigation buttons still only switch tabs, disclosures still only reveal local UI sections, and copy-only setup guidance remains non-executing.

## Task 124 note — Settings tab foundation

The Settings tab is read-only in its first version. It reuses already loaded workspace dashboard and model summary data plus the existing frontend `API_BASE_URL` constant. It does not introduce new API calls or persistence behavior.

Future tasks may add localStorage-backed UI preferences or backend settings endpoints after the desired settings model is agreed.

## 9. Settings Screen Local Preferences

The Settings screen currently uses no backend write endpoints. It displays
backend URL, workspace identity, current model selections, and safety posture
from already-loaded frontend read models.

Browser-local preferences are stored in `localStorage`:

- Theme: system, light, or dark.
- Density: comfortable or compact.
- Default Ask source snippets: 3, 5, 8, or 10.
- Workspace landing tab preference.

These settings must remain UI-only unless a future task intentionally introduces
a backend settings model. They must not execute commands, scan, index, rebuild
search context, restart services, or change active runtime/model configuration.

## Task 126 note — Dark Theme Token Repair

Task 126 changed CSS theme tokens and dark-mode overrides only. It introduced no new frontend API calls and no backend contract changes. Theme selection remains browser-local through the existing Settings/localStorage flow.

## Task 127: Remaining Dark Surface Fixes

No API contract changes. The frontend now applies additional dark-mode surface
overrides for Ask, Capabilities, and Activity. The Capabilities UI also formats
backend-provided labels/descriptions so older `LLM` wording is shown with
beginner-friendly AI model wording.


## Task 128 — Settings reset and preference clarity

- Added browser-local save feedback for Settings preferences.
- Added a two-step reset flow for local UI preferences only.
- Reset affects theme, density, landing tab, and default source snippets in localStorage.
- No backend API, command execution, scan, index, rebuild, or model/runtime change is introduced.

## Task 129 note — Settings export/import preferences

The Settings export/import flow is frontend-only. It reads and writes the existing browser-local preferences object used by the Settings screen and Ask default source snippet selection. It introduces no backend API calls and no API contract changes.

Imported JSON is validated before use and only supported UI preference values are accepted. The flow must remain limited to browser-local UI preferences unless a future task explicitly designs backend-backed settings.

## Task 130 note — Backend URL preference

The frontend API client now has a browser-local configurable base URL. The default still comes from `VITE_API_BASE_URL` or `http://127.0.0.1:8000`, but Settings can save a different `apiBaseUrl` value into the existing preferences object.

The setting changes only the frontend fetch target. It introduces no backend API contract changes and no new backend calls. Users must explicitly refresh workspace data after changing the URL.

## Task 131 note

Settings backup/import remains browser-local. The backup tools are now hidden behind a disclosure and still do not call backend APIs.

## Task 132 note — Settings final polish

The Settings screen now includes a local navigation action from AI defaults to
the existing Models tab. This is a frontend tab switch only; it does not call a
backend endpoint, mutate model selection, run comparisons, rebuild search
context, or execute commands.

## Task 133 note — Workspace creation onboarding

The frontend now uses the existing `POST /workspaces` endpoint from an explicit create-workspace form. The request is user-submitted and includes workspace name, local project path, assistant mode, and privacy mode.

This onboarding flow does not add backend contracts beyond the existing workspace create endpoint. It does not trigger scan, index, rebuild search context, model calls, runtime changes, or shell command execution automatically. After creation, the frontend refreshes read-only workspace state and selects the new workspace.

## Task 134 — Branding, assistant mode safety, and CI

The frontend product name is now **AI Private Workspace**. Branding preferences are browser-local only and do not use backend APIs.

The workspace creation form displays **Support mode** but submits the backend-supported assistant mode `support_incident`. This keeps UI copy friendly while matching the backend assistant profile registry.

GitHub Actions CI now lives in `.github/workflows/ci.yml` and runs frontend `npm run typecheck`, frontend `npm run build`, and backend `pytest`.

## Task 135 — Workspace archive UI

The sidebar now surfaces the reversible archive lifecycle action for active workspaces. The UI uses a two-step confirmation and calls `POST /workspaces/{workspace_id}/archive` only after explicit user confirmation.

Archived workspaces are removed from the default active overview after refresh. This is not a hard delete and does not remove local project files. Restore/archive browsing remains a future Settings or workspace-management surface.


### Task 136 - Archived workspace restore UI

The frontend now uses `GET /workspaces/overview?include_archived=true` to populate an optional archived workspace section in the sidebar and `POST /workspaces/{workspace_id}/restore` to restore archived workspaces. The restore action is explicit, does not delete local files, and does not trigger scan/index/rebuild/model calls. The Add project screen was also polished for a clearer first-run onboarding experience.

## Task 137 note — Explicit setup actions

The frontend now exposes explicit Overview setup actions for workspace preparation:

- `POST /workspaces/{workspace_id}/scan` for user-clicked project scans.
- `POST /workspaces/{workspace_id}/index` for user-clicked search context builds.

These actions are local backend API calls, not shell command execution. They are never triggered automatically after workspace creation. The UI refreshes read-only dashboard/model/sidebar state after each successful action.

The sidebar also separates active and archived workspace sections more clearly. `Show archived` adds the archived section but should not remove Archive controls from active workspaces.


## Task 138 frontend notes

- Overview now includes a read-only Workspace skills panel built from existing dashboard state.
- Ask now shows the current assistant focus using the workspace assistant mode.
- No new backend endpoints were added.
- Future skill customization should be implemented as an explicit settings/workspace flow, not as automatic prompt changes hidden from the user.

## Task 139 frontend-only Skill Library

The Skill Library is currently browser-local and uses no new backend endpoints. Presets and custom instructions are stored in the existing local preferences object. Future backend integration should expose an explicit workspace skill/profile API before these instructions affect model prompts.

## Task 140 — Skill context in Ask requests

`POST /workspaces/{workspace_id}/ask-selected` now accepts an optional `skill_context` array from the frontend. The frontend builds it from enabled browser-local skill presets in Settings.

Example payload:

```json
{
  "question": "What should I review before deployment?",
  "limit": 5,
  "skill_context": [
    {
      "id": "devops",
      "name": "DevOps",
      "custom_instructions": "Answer as a DevOps/platform assistant..."
    }
  ]
}
```

This is an explicit Ask-only payload. It does not save skills to the backend, execute commands, scan files, rebuild context, or change model/runtime settings.
