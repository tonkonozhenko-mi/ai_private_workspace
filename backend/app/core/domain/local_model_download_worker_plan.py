from dataclasses import dataclass


@dataclass(frozen=True)
class LocalModelDownloadWorkerStep:
    id: str
    title: str
    description: str
    status: str


@dataclass(frozen=True)
class LocalModelDownloadWorkerGuardrail:
    id: str
    label: str
    detail: str


@dataclass(frozen=True)
class LocalModelDownloadWorkerPlan:
    title: str
    summary: str
    status: str
    worker_enabled: bool
    execution_mode: str
    approved_command_pattern: str
    allowed_provider: str
    steps: list[LocalModelDownloadWorkerStep]
    guardrails: list[LocalModelDownloadWorkerGuardrail]
    future_endpoints: list[str]
    user_flow: list[str]


def build_local_model_download_worker_plan() -> LocalModelDownloadWorkerPlan:
    return LocalModelDownloadWorkerPlan(
        title="Controlled backend model download worker",
        summary=(
            "The next implementation stage is a backend-only worker for approved Ollama downloads. "
            "The frontend will request and observe downloads, but it will never execute shell commands."
        ),
        status="design_ready",
        worker_enabled=False,
        execution_mode="backend_only_after_explicit_approval",
        approved_command_pattern="ollama pull <catalog-model-name>",
        allowed_provider="ollama",
        steps=[
            LocalModelDownloadWorkerStep(
                id="draft",
                title="Create download draft",
                description="The user chooses a catalog model and the backend records a pending intent.",
                status="implemented",
            ),
            LocalModelDownloadWorkerStep(
                id="approve",
                title="Approve exact model download",
                description="The user approves one exact catalog model and command. Custom shell text is not accepted.",
                status="planned",
            ),
            LocalModelDownloadWorkerStep(
                id="execute",
                title="Run from backend worker only",
                description="A backend worker runs a narrowly allowlisted Ollama command and records progress/status.",
                status="planned",
            ),
            LocalModelDownloadWorkerStep(
                id="verify",
                title="Verify availability",
                description="The backend checks the installed model list before offering it as ready for Ask or indexing.",
                status="planned",
            ),
        ],
        guardrails=[
            LocalModelDownloadWorkerGuardrail(
                id="no_frontend_shell",
                label="No frontend shell",
                detail="The browser UI never runs terminal commands, scripts, MCP tools, or model downloads.",
            ),
            LocalModelDownloadWorkerGuardrail(
                id="catalog_only",
                label="Catalog allowlist first",
                detail="The first executable version should accept only known Ollama models from the local catalog.",
            ),
            LocalModelDownloadWorkerGuardrail(
                id="exact_command",
                label="Exact command generation",
                detail="The backend generates the command from provider/model fields; users cannot submit arbitrary shell text.",
            ),
            LocalModelDownloadWorkerGuardrail(
                id="observable_status",
                label="Observable progress",
                detail="Downloads need pending/running/succeeded/failed status and safe stdout/stderr summaries.",
            ),
            LocalModelDownloadWorkerGuardrail(
                id="no_rebuild_side_effect",
                label="No hidden rebuilds",
                detail="Installing an embedding model must not rebuild indexes until the user explicitly starts that action.",
            ),
        ],
        future_endpoints=[
            "POST /models/local-install-drafts/{id}/approve",
            "POST /models/local-install-drafts/{id}/run",
            "GET /models/local-install-jobs/{id}",
            "GET /models/installed",
        ],
        user_flow=[
            "Choose a recommended model.",
            "Create a download draft.",
            "Review size, purpose, and exact command.",
            "Approve the backend download when worker execution exists.",
            "Watch progress and verify that the model is installed.",
            "Save the model as workspace preference or build context explicitly.",
        ],
    )
