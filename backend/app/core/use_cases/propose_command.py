from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.domain.command_policy import evaluate_command_policy
from app.core.domain.command_risk import classify_command_risk
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.ports.workspace_repository import WorkspaceRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)
from app.core.use_cases.command_errors import CommandWorkspaceNotFoundError


@dataclass(frozen=True)
class ProposeCommandInput:
    workspace_id: str
    command: str
    cwd: str
    reason: str


class ProposeCommandUseCase:
    def __init__(
        self,
        workspace_repository: WorkspaceRepositoryPort,
        command_repository: CommandRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.workspace_repository = workspace_repository
        self.command_repository = command_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: ProposeCommandInput) -> CommandProposal:
        workspace = self.workspace_repository.get(request.workspace_id)
        if workspace is None:
            raise CommandWorkspaceNotFoundError("Workspace not found")

        risk = classify_command_risk(request.command)
        policy_decision = evaluate_command_policy(request.command, risk)
        proposal = CommandProposal(
            id=str(uuid4()),
            workspace_id=request.workspace_id,
            command=request.command,
            cwd=request.cwd,
            reason=request.reason,
            risk=risk,
            status=CommandStatus.PENDING.value,
            created_at=datetime.now(UTC).isoformat(),
            approved_at=None,
            rejected_at=None,
            executed_at=None,
            stdout=None,
            stderr=None,
            exit_code=None,
            policy_allowed=policy_decision.allowed,
            policy_mode=policy_decision.mode,
            policy_reason=policy_decision.reason,
        )
        created_proposal = self.command_repository.create(proposal)
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=created_proposal.workspace_id,
                    event_type="command_proposed",
                    title="Command proposed",
                    summary=f"Proposed command: {created_proposal.command}",
                    metadata={
                        "command_id": created_proposal.id,
                        "risk": created_proposal.risk,
                        "policy_mode": created_proposal.policy_mode or "",
                    },
                )
            )
        return created_proposal
