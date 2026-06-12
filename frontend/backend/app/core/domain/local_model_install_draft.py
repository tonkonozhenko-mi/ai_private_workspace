from dataclasses import dataclass

from app.core.domain.command import CommandProposal
from app.core.domain.model_catalog import LocalModelDefinition


@dataclass(frozen=True)
class LocalModelInstallDraft:
    workspace_id: str
    provider: str
    model: str
    model_type: str
    display_name: str
    purpose: str
    estimated_size: str | None
    command: str
    status: str
    safety_summary: str
    approval_required: bool
    execution_supported: bool
    next_steps: list[str]
    command_proposal: CommandProposal


def build_local_model_install_draft(
    *,
    workspace_id: str,
    model: LocalModelDefinition,
    command_proposal: CommandProposal,
) -> LocalModelInstallDraft:
    return LocalModelInstallDraft(
        workspace_id=workspace_id,
        provider=model.provider,
        model=model.model_name,
        model_type=model.model_type,
        display_name=model.display_name,
        purpose=_purpose_for(model),
        estimated_size=model.estimated_size,
        command=f"ollama pull {model.model_name}",
        status="draft_created",
        safety_summary=(
            "This creates a reviewable download draft only. The app records the user's intent "
            "but does not download, start, rebuild, or restart anything."
        ),
        approval_required=True,
        execution_supported=False,
        next_steps=[
            "Review the model name, size, and purpose.",
            "Copy the command or approve the draft as an intent record.",
            "Run the download outside the UI until controlled backend execution is implemented.",
            "Verify the model with ollama list, then save it as the workspace preference.",
        ],
        command_proposal=command_proposal,
    )


def _purpose_for(model: LocalModelDefinition) -> str:
    if model.model_type == "embedding":
        return "Search context model used to index and retrieve local workspace chunks."
    if "coder" in model.model_name.lower():
        return "AI answer model optimized for code, DevOps, CI/CD, Terraform, and infrastructure work."
    return "AI answer model for general local workspace questions."
