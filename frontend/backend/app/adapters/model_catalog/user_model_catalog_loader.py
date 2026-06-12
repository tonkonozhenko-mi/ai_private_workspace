import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.domain.model_catalog import (
    LocalModelDefinition,
    ModelCatalogResult,
    ModelCatalogWarning,
)


class _UserModelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_type: Literal["llm", "embedding"]
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    capabilities: list[str]
    recommended_for_profiles: list[str]
    recommended_laptop_profiles: list[str]
    estimated_size: str | None
    context_window: int | None
    embedding_dimension: int | None
    quality_tier: Literal["basic", "good", "strong", "experimental"]
    speed_tier: Literal["slow", "medium", "fast"]
    local_only: bool
    notes: list[str]


class UserModelCatalogLoader:
    def __init__(self, catalog_path: str) -> None:
        self.catalog_path = catalog_path

    def load(self) -> ModelCatalogResult:
        if not self.catalog_path.strip():
            return ModelCatalogResult(models=[], warnings=[])

        path = Path(self.catalog_path)
        if not path.is_file():
            return self._warning_result(
                code="user_catalog_not_found",
                message=f"User model catalog file was not found: {path}",
                source=str(path),
            )

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return self._warning_result(
                code="user_catalog_invalid_json",
                message=f"User model catalog contains malformed JSON: {exc.msg}",
                source=str(path),
            )
        except (OSError, UnicodeError) as exc:
            return self._warning_result(
                code="user_catalog_read_error",
                message=f"User model catalog could not be read: {exc}",
                source=str(path),
            )

        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            return self._warning_result(
                code="user_catalog_invalid_format",
                message="User model catalog must be a JSON object containing a models list.",
                source=str(path),
            )

        models: list[LocalModelDefinition] = []
        warnings: list[ModelCatalogWarning] = []
        for index, raw_model in enumerate(payload["models"]):
            source = f"{path}#models[{index}]"
            try:
                model = _UserModelDefinition.model_validate(raw_model)
            except ValidationError as exc:
                warnings.append(
                    ModelCatalogWarning(
                        code="invalid_user_model",
                        message=self._validation_message(exc),
                        source=source,
                    )
                )
                continue
            models.append(LocalModelDefinition(**model.model_dump()))

        return ModelCatalogResult(models=models, warnings=warnings)

    @staticmethod
    def _warning_result(
        code: str,
        message: str,
        source: str | None,
    ) -> ModelCatalogResult:
        return ModelCatalogResult(
            models=[],
            warnings=[ModelCatalogWarning(code=code, message=message, source=source)],
        )

    @staticmethod
    def _validation_message(error: ValidationError) -> str:
        details = []
        for item in error.errors():
            location = ".".join(str(part) for part in item["loc"]) or "model"
            details.append(f"{location}: {item['msg']}")
        return "Invalid user model metadata: " + "; ".join(details)
