from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSetupAction:
    id: str
    title: str
    description: str
    command: str | None
    status: str
    reason: str
    category: str


@dataclass(frozen=True)
class RuntimeSetupGuide:
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str
    container_runtime: str
    overall_status: str
    actions: list[RuntimeSetupAction]
    notes: list[str]
