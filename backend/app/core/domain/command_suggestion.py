from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSuggestion:
    id: str
    title: str
    command: str
    cwd: str
    reason: str
    risk: str
    category: str
    requires_approval: bool
