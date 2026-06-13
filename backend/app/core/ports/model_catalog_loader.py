from typing import Protocol

from app.core.domain.model_catalog import LocalModelDefinition, ModelCatalogResult


class ModelCatalogLoaderPort(Protocol):
    def load(self) -> ModelCatalogResult:
        """Load user-defined model metadata and validation warnings."""

    def save(self, models: list[LocalModelDefinition]) -> None:
        """Persist user-defined model metadata."""


ModelCatalogLoader = ModelCatalogLoaderPort
