from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    path: str
    name: str | None = None
