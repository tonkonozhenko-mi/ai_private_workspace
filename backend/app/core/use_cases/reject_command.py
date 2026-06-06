from dataclasses import dataclass, replace
from datetime import UTC, datetime

from app.core.domain.command import CommandProposal, CommandStatus
from app.core.ports.command_repository import CommandRepositoryPort
from app.core.ports.timeline_repository import TimelineRepositoryPort
from app.core.use_cases.add_timeline_event import (
    AddTimelineEventInput,
    AddTimelineEventUseCase,
)
from app.core.use_cases.command_errors import CommandInvalidStatusError, CommandNotFoundError


@dataclass(frozen=True)
class RejectCommandInput:
    command_id: str


class RejectCommandUseCase:
    def __init__(
        self,
        command_repository: CommandRepositoryPort,
        timeline_repository: TimelineRepositoryPort | None = None,
    ) -> None:
        self.command_repository = command_repository
        self.timeline_repository = timeline_repository

    def execute(self, request: RejectCommandInput) -> CommandProposal:
        proposal = self.command_repository.get(request.command_id)
        if proposal is None:
            raise CommandNotFoundError("Command not found")
        if proposal.status != CommandStatus.PENDING.value:
            raise CommandInvalidStatusError("Only pending commands can be rejected")

        rejected_proposal = replace(
            proposal,
            status=CommandStatus.REJECTED.value,
            rejected_at=datetime.now(UTC).isoformat(),
        )
        updated_proposal = self.command_repository.update(rejected_proposal)
        if self.timeline_repository is not None:
            AddTimelineEventUseCase(self.timeline_repository).execute(
                AddTimelineEventInput(
                    workspace_id=updated_proposal.workspace_id,
                    event_type="command_rejected",
                    title="Command rejected",
                    summary=f"Rejected command: {updated_proposal.command}",
                    metadata={"command_id": updated_proposal.id},
                )
            )
        return updated_proposal
