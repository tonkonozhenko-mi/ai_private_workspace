from pydantic import BaseModel

from app.core.domain.command import CommandProposal


class ProposeCommandRequest(BaseModel):
    command: str
    cwd: str
    reason: str


class CommandProposalResponse(BaseModel):
    id: str
    workspace_id: str
    command: str
    cwd: str
    reason: str
    risk: str
    status: str
    created_at: str
    approved_at: str | None
    rejected_at: str | None
    executed_at: str | None
    stdout: str | None
    stderr: str | None
    exit_code: int | None
    policy_allowed: bool | None
    policy_mode: str | None
    policy_reason: str | None


def to_command_proposal_response(
    proposal: CommandProposal,
) -> CommandProposalResponse:
    return CommandProposalResponse(
        id=proposal.id,
        workspace_id=proposal.workspace_id,
        command=proposal.command,
        cwd=proposal.cwd,
        reason=proposal.reason,
        risk=proposal.risk,
        status=proposal.status,
        created_at=proposal.created_at,
        approved_at=proposal.approved_at,
        rejected_at=proposal.rejected_at,
        executed_at=proposal.executed_at,
        stdout=proposal.stdout,
        stderr=proposal.stderr,
        exit_code=proposal.exit_code,
        policy_allowed=proposal.policy_allowed,
        policy_mode=proposal.policy_mode,
        policy_reason=proposal.policy_reason,
    )
