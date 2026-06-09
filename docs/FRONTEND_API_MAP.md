# Frontend API Map

This document maps the current Private Project AI Workbench backend to the
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
  appropriate.

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
