from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import (
    command_repository,
    command_runner,
    project_scan_repository,
    timeline_repository,
    workspace_repository,
)
from app.api.schemas.command_schemas import (
    CommandProposalResponse,
    ProposeCommandRequest,
    to_command_proposal_response,
)
from app.api.schemas.command_suggestion_schemas import (
    CommandSuggestionResponse,
    to_command_suggestion_response,
)
from app.core.use_cases.approve_command import ApproveCommandInput, ApproveCommandUseCase
from app.core.use_cases.command_errors import (
    CommandInvalidStatusError,
    CommandNotFoundError,
    CommandWorkspaceNotFoundError,
)
from app.core.use_cases.execute_approved_command import (
    ExecuteApprovedCommandInput,
    ExecuteApprovedCommandUseCase,
)
from app.core.use_cases.list_workspace_commands import (
    ListWorkspaceCommandsInput,
    ListWorkspaceCommandsUseCase,
)
from app.core.use_cases.propose_command import ProposeCommandInput, ProposeCommandUseCase
from app.core.use_cases.reject_command import RejectCommandInput, RejectCommandUseCase
from app.core.use_cases.suggest_workspace_commands import (
    SuggestWorkspaceCommandsInput,
    SuggestWorkspaceCommandsUseCase,
)

router = APIRouter(tags=["commands"])


@router.post(
    "/workspaces/{workspace_id}/commands",
    response_model=CommandProposalResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_command(
    workspace_id: str,
    request: ProposeCommandRequest,
) -> CommandProposalResponse:
    use_case = ProposeCommandUseCase(
        workspace_repository=workspace_repository,
        command_repository=command_repository,
        timeline_repository=timeline_repository,
    )

    try:
        proposal = use_case.execute(
            ProposeCommandInput(
                workspace_id=workspace_id,
                command=request.command,
                cwd=request.cwd,
                reason=request.reason,
            )
        )
    except CommandWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return to_command_proposal_response(proposal)


@router.get(
    "/workspaces/{workspace_id}/commands",
    response_model=list[CommandProposalResponse],
)
def list_workspace_commands(workspace_id: str) -> list[CommandProposalResponse]:
    use_case = ListWorkspaceCommandsUseCase(
        workspace_repository=workspace_repository,
        command_repository=command_repository,
    )

    try:
        proposals = use_case.execute(ListWorkspaceCommandsInput(workspace_id=workspace_id))
    except CommandWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [to_command_proposal_response(proposal) for proposal in proposals]


@router.get(
    "/workspaces/{workspace_id}/commands/suggestions",
    response_model=list[CommandSuggestionResponse],
)
def suggest_workspace_commands(workspace_id: str) -> list[CommandSuggestionResponse]:
    use_case = SuggestWorkspaceCommandsUseCase(
        workspace_repository=workspace_repository,
        project_scan_repository=project_scan_repository,
    )

    try:
        suggestions = use_case.execute(SuggestWorkspaceCommandsInput(workspace_id=workspace_id))
    except CommandWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [to_command_suggestion_response(suggestion) for suggestion in suggestions]


@router.post(
    "/commands/{command_id}/approve",
    response_model=CommandProposalResponse,
)
def approve_command(command_id: str) -> CommandProposalResponse:
    use_case = ApproveCommandUseCase(
        command_repository=command_repository,
        timeline_repository=timeline_repository,
    )
    proposal = _execute_command_mutation(
        lambda: use_case.execute(ApproveCommandInput(command_id=command_id))
    )
    return to_command_proposal_response(proposal)


@router.post(
    "/commands/{command_id}/reject",
    response_model=CommandProposalResponse,
)
def reject_command(command_id: str) -> CommandProposalResponse:
    use_case = RejectCommandUseCase(
        command_repository=command_repository,
        timeline_repository=timeline_repository,
    )
    proposal = _execute_command_mutation(
        lambda: use_case.execute(RejectCommandInput(command_id=command_id))
    )
    return to_command_proposal_response(proposal)


@router.post(
    "/commands/{command_id}/execute",
    response_model=CommandProposalResponse,
)
def execute_command(command_id: str) -> CommandProposalResponse:
    use_case = ExecuteApprovedCommandUseCase(
        command_repository=command_repository,
        command_runner=command_runner,
        workspace_repository=workspace_repository,
        timeline_repository=timeline_repository,
    )
    proposal = _execute_command_mutation(
        lambda: use_case.execute(ExecuteApprovedCommandInput(command_id=command_id))
    )
    return to_command_proposal_response(proposal)


def _execute_command_mutation(action):
    try:
        return action()
    except CommandNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CommandInvalidStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except CommandWorkspaceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
