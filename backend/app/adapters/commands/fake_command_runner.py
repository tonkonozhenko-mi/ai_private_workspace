from app.core.ports.command_runner import CommandResult


class FakeCommandRunner:
    def run(self, command: str, cwd: str) -> CommandResult:
        return CommandResult(
            command=command,
            stdout=f"fake execution: {command}",
            stderr="",
            exit_code=0,
        )
