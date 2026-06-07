from dataclasses import dataclass

from app.core.domain.model_catalog import LocalModelDefinition
from app.core.domain.model_catalog_registry import ModelCatalogRegistry


@dataclass(frozen=True)
class ListModelCatalogInput:
    model_type: str | None = None
    provider: str | None = None
    assistant_profile_id: str | None = None


class ListModelCatalogUseCase:
    def __init__(self, registry: ModelCatalogRegistry | None = None) -> None:
        self.registry = registry or ModelCatalogRegistry()

    def execute(self, request: ListModelCatalogInput) -> list[LocalModelDefinition]:
        model_type = request.model_type.lower() if request.model_type else None
        provider = request.provider.lower() if request.provider else None

        return [
            model
            for model in self.registry.list_models()
            if (model_type is None or model.model_type == model_type)
            and (provider is None or model.provider == provider)
            and (
                request.assistant_profile_id is None
                or request.assistant_profile_id in model.recommended_for_profiles
            )
        ]
