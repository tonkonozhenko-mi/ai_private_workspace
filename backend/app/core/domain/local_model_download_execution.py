from dataclasses import dataclass

from app.core.domain.command import CommandProposal


@dataclass(frozen=True)
class LocalModelDownloadExecutionCapability:
    title: str
    status: str
    execution_enabled: bool
    execution_mode: str
    safety_summary: str
    requirements: list[str]
    disabled_reason: str | None


@dataclass(frozen=True)
class LocalModelDownloadExecutionResult:
    command_id: str
    workspace_id: str
    provider: str
    model: str
    display_name: str
    status: str
    execution_status: str
    safety_summary: str
    command_proposal: CommandProposal
    next_steps: list[str]


def build_local_model_download_execution_capability(
    *,
    execution_enabled: bool,
    command_runner: str,
) -> LocalModelDownloadExecutionCapability:
    disabled_reason = None
    if not execution_enabled:
        disabled_reason = (
            "Backend model download execution is disabled by default. Set "
            "MODEL_DOWNLOAD_EXECUTION_ENABLED=true only for a trusted local desktop runtime."
        )
    elif command_runner != "local":
        disabled_reason = (
            "Backend execution is enabled, but COMMAND_RUNNER is not local. "
            "Use COMMAND_RUNNER=local for real Ollama downloads."
        )

    ready = execution_enabled and command_runner == "local"
    return LocalModelDownloadExecutionCapability(
        title="Approved local model downloads",
        status="ready" if ready else "disabled",
        execution_enabled=ready,
        execution_mode="backend_only_after_explicit_approval",
        safety_summary=(
            "The browser never runs shell commands. A model download can run only from the backend, "
            "only for an Ollama model that exists in the local allowlist catalog, and only after the "
            "user explicitly creates and runs a download draft."
        ),
        requirements=[
            "The model must be in the local model catalog.",
            "The command must match exactly: ollama pull <catalog-model-name>.",
            "The command runner must be local and configured by the desktop runtime.",
            "Installing an embedding model must not rebuild indexes automatically.",
        ],
        disabled_reason=disabled_reason,
    )
