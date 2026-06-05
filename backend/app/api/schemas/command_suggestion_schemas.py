from pydantic import BaseModel

from app.core.domain.command_suggestion import CommandSuggestion


class CommandSuggestionResponse(BaseModel):
    id: str
    title: str
    command: str
    cwd: str
    reason: str
    risk: str
    category: str
    requires_approval: bool


def to_command_suggestion_response(
    suggestion: CommandSuggestion,
) -> CommandSuggestionResponse:
    return CommandSuggestionResponse(
        id=suggestion.id,
        title=suggestion.title,
        command=suggestion.command,
        cwd=suggestion.cwd,
        reason=suggestion.reason,
        risk=suggestion.risk,
        category=suggestion.category,
        requires_approval=suggestion.requires_approval,
    )
