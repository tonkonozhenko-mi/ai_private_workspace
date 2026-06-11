from pydantic import BaseModel

from app.api.schemas.command_schemas import CommandProposalResponse, to_command_proposal_response
from app.core.domain.local_model_download_execution import (
    LocalModelDownloadExecutionCapability,
    LocalModelDownloadExecutionResult,
)


class LocalModelDownloadExecutionCapabilityResponse(BaseModel):
    title: str
    status: str
    execution_enabled: bool
    execution_mode: str
    safety_summary: str
    requirements: list[str]
    disabled_reason: str | None


class LocalModelDownloadExecutionResultResponse(BaseModel):
    command_id: str
    workspace_id: str
    provider: str
    model: str
    display_name: str
    status: str
    execution_status: str
    safety_summary: str
    command_proposal: CommandProposalResponse
    next_steps: list[str]


def to_local_model_download_execution_capability_response(
    capability: LocalModelDownloadExecutionCapability,
) -> LocalModelDownloadExecutionCapabilityResponse:
    return LocalModelDownloadExecutionCapabilityResponse(
        title=capability.title,
        status=capability.status,
        execution_enabled=capability.execution_enabled,
        execution_mode=capability.execution_mode,
        safety_summary=capability.safety_summary,
        requirements=capability.requirements,
        disabled_reason=capability.disabled_reason,
    )


def to_local_model_download_execution_result_response(
    result: LocalModelDownloadExecutionResult,
) -> LocalModelDownloadExecutionResultResponse:
    return LocalModelDownloadExecutionResultResponse(
        command_id=result.command_id,
        workspace_id=result.workspace_id,
        provider=result.provider,
        model=result.model,
        display_name=result.display_name,
        status=result.status,
        execution_status=result.execution_status,
        safety_summary=result.safety_summary,
        command_proposal=to_command_proposal_response(result.command_proposal),
        next_steps=result.next_steps,
    )
