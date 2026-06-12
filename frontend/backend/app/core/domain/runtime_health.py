from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeComponentHealth:
    name: str
    configured: bool
    healthy: bool
    status: str
    details: str | None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeHealth:
    status: str
    components: list[RuntimeComponentHealth]
    configuration: dict[str, str]
