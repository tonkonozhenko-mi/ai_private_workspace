from typing import Protocol

from app.core.domain.command import CommandProposal


class CommandRepositoryPort(Protocol):
    def create(self, proposal: CommandProposal) -> CommandProposal:
        """Persist a command proposal."""

    def get(self, command_id: str) -> CommandProposal | None:
        """Return a command proposal by id, if it exists."""

    def list_by_workspace(self, workspace_id: str) -> list[CommandProposal]:
        """Return all command proposals for a workspace."""

    def update(self, proposal: CommandProposal) -> CommandProposal:
        """Persist an updated command proposal."""
