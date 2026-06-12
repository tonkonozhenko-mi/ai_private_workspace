from app.core.domain.command import CommandProposal


class InMemoryCommandRepository:
    def __init__(self) -> None:
        self._commands: dict[str, CommandProposal] = {}

    def create(self, proposal: CommandProposal) -> CommandProposal:
        self._commands[proposal.id] = proposal
        return proposal

    def get(self, command_id: str) -> CommandProposal | None:
        return self._commands.get(command_id)

    def list_by_workspace(self, workspace_id: str) -> list[CommandProposal]:
        return [
            proposal
            for proposal in self._commands.values()
            if proposal.workspace_id == workspace_id
        ]

    def update(self, proposal: CommandProposal) -> CommandProposal:
        self._commands[proposal.id] = proposal
        return proposal
