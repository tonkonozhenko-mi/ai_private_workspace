from dataclasses import dataclass


@dataclass(frozen=True)
class SetupCommand:
    id: str
    title: str
    command: str
    description: str
    category: str
    required: bool
    risk: str
    can_be_proposed: bool


@dataclass(frozen=True)
class OnboardingSetupCommands:
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str
    commands: list[SetupCommand]
    notes: list[str]
