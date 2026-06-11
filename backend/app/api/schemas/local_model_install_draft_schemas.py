from pydantic import BaseModel

from app.api.schemas.command_schemas import CommandProposalResponse, to_command_proposal_response
from app.core.domain.local_model_install_draft import LocalModelInstallDraft


class CreateLocalModelInstallDraftRequest(BaseModel):
    workspace_id: str
    provider: str
    model: str
    model_type: str | None = None


class LocalModelInstallDraftResponse(BaseModel):
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
    command_proposal: CommandProposalResponse


def to_local_model_install_draft_response(
    draft: LocalModelInstallDraft,
) -> LocalModelInstallDraftResponse:
    return LocalModelInstallDraftResponse(
        workspace_id=draft.workspace_id,
        provider=draft.provider,
        model=draft.model,
        model_type=draft.model_type,
        display_name=draft.display_name,
        purpose=draft.purpose,
        estimated_size=draft.estimated_size,
        command=draft.command,
        status=draft.status,
        safety_summary=draft.safety_summary,
        approval_required=draft.approval_required,
        execution_supported=draft.execution_supported,
        next_steps=draft.next_steps,
        command_proposal=to_command_proposal_response(draft.command_proposal),
    )
