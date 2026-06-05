from app.core.ports.command_runner import CommandResult


class FakeCommandRunner:
    def run(self, command: str, approved: bool) -> CommandResult:
        if not approved:
            return CommandResult(
                command=command,
                return_code=1,
                stdout="",
                stderr="Command execution requires user approval.",
            )

        return CommandResult(
            command=command,
            return_code=0,
            stdout="Fake command runner did not execute a real command.",
            stderr="",
        )
