from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeComponentHealth:
    name: str
    configured: bool
    healthy: bool
    status: str
    details: str | None


@dataclass(frozen=True)
class RuntimeHealth:
    status: str
    components: list[RuntimeComponentHealth]
    configuration: dict[str, str]
