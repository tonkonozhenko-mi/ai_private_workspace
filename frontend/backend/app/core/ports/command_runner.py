from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    command: str
    stdout: str
    stderr: str
    exit_code: int


class CommandRunnerPort(Protocol):
    def run(
        self,
        command: str,
        cwd: str,
        allowed_root: str | None = None,
    ) -> CommandResult:
        """Run an approved terminal command."""


CommandRunner = CommandRunnerPort
