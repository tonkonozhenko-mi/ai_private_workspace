from typing import Protocol

from app.core.domain.model_catalog import ModelCatalogResult


class ModelCatalogLoaderPort(Protocol):
    def load(self) -> ModelCatalogResult:
        """Load user-defined model metadata and validation warnings."""


ModelCatalogLoader = ModelCatalogLoaderPort
