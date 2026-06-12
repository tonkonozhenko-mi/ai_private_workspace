from app.core.domain.model_catalog import ModelCatalogReloadResult
from app.core.domain.model_catalog_registry import ModelCatalogRegistry


class ReloadModelCatalogUseCase:
    def __init__(self, registry: ModelCatalogRegistry) -> None:
        self.registry = registry

    def execute(self) -> ModelCatalogReloadResult:
        return self.registry.reload()
