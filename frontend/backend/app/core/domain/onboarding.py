from dataclasses import dataclass


@dataclass(frozen=True)
class LaptopProfile:
    id: str
    name: str
    description: str


@dataclass(frozen=True)
class OnboardingStep:
    id: str
    title: str
    description: str
    required: bool
    status: str


@dataclass(frozen=True)
class OnboardingPlan:
    assistant_profile_id: str
    laptop_profile_id: str
    privacy_mode: str
    recommended_runtime: dict[str, str]
    recommended_models: dict[str, str]
    steps: list[OnboardingStep]
    notes: list[str]
