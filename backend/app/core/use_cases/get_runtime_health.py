from app.core.domain.runtime_health import RuntimeHealth
from app.core.ports.runtime_health_checker import RuntimeHealthCheckerPort


class GetRuntimeHealthUseCase:
    def __init__(
        self,
        health_checkers: list[RuntimeHealthCheckerPort],
        configuration: dict[str, str],
    ) -> None:
        self.health_checkers = health_checkers
        self.configuration = configuration

    def execute(self) -> RuntimeHealth:
        components = [checker.check() for checker in self.health_checkers]
        degraded = any(component.configured and not component.healthy for component in components)
        return RuntimeHealth(
            status="degraded" if degraded else "ok",
            components=components,
            configuration=dict(self.configuration),
        )
