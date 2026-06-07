from typing import Protocol

from app.core.domain.runtime_health import RuntimeComponentHealth


class RuntimeHealthCheckerPort(Protocol):
    def check(self) -> RuntimeComponentHealth:
        """Return lightweight health information for one runtime component."""
