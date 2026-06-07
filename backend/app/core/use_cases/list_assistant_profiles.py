from app.core.domain.assistant_profile import AssistantProfile
from app.core.domain.assistant_profile_registry import AssistantProfileRegistry


class ListAssistantProfilesUseCase:
    def __init__(
        self,
        profile_registry: AssistantProfileRegistry | None = None,
    ) -> None:
        self.profile_registry = profile_registry or AssistantProfileRegistry()

    def execute(self) -> list[AssistantProfile]:
        return self.profile_registry.list_profiles()
