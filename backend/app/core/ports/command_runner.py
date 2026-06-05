from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    command: str
    return_code: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, command: str, approved: bool) -> CommandResult:
        """Run a terminal command only when approval has already been granted."""
