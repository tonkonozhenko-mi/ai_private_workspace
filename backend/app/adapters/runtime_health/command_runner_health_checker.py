from app.core.domain.runtime_health import RuntimeComponentHealth


class CommandRunnerHealthChecker:
    def __init__(self, command_runner: str) -> None:
        self.command_runner = command_runner.lower()

    def check(self) -> RuntimeComponentHealth:
        if self.command_runner == "fake":
            return RuntimeComponentHealth(
                name="command_runner",
                configured=True,
                healthy=True,
                status="ok",
                details="Fake command runner is configured; no real commands are executed.",
            )
        if self.command_runner == "local":
            return RuntimeComponentHealth(
                name="command_runner",
                configured=True,
                healthy=True,
                status="ok",
                details=(
                    "Local command runner is configured; approval and execution "
                    "policy are still required."
                ),
            )
        return RuntimeComponentHealth(
            name="command_runner",
            configured=bool(self.command_runner),
            healthy=False,
            status="unknown",
            details=f"Unknown command runner mode: {self.command_runner or 'empty'}.",
        )
