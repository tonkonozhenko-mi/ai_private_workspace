from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantProfile:
    mode: str
    privacy_mode: str
