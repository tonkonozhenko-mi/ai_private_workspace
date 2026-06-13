"""Load the curated model catalog from a hosted JSON manifest, with caching.

This lets new models be added to the picker by updating a small JSON file you
host, without shipping a new app version. It fits the local-first principle:
the manifest is only ever *read* over the network (a plain GET), never used to
send any project data out.

Behaviour:
- If no URL is configured, this loader is inert (empty result).
- On load, it tries to fetch the manifest, writes it to a local cache file, and
  parses it with the same strict validation as the file-based loader.
- If the network is unavailable, it falls back to the last cached manifest, so
  the app still works fully offline after the first successful fetch.

The manifest format is identical to the user catalog file: {"models": [ ... ]}.
"""

from pathlib import Path

from app.adapters.model_catalog.user_model_catalog_loader import UserModelCatalogLoader
from app.core.domain.model_catalog import (
    LocalModelDefinition,
    ModelCatalogResult,
    ModelCatalogWarning,
)


class RemoteModelCatalogLoader:
    def __init__(
        self,
        url: str,
        cache_path: str,
        timeout_seconds: int = 5,
    ) -> None:
        self.url = url
        self.cache_path = cache_path
        self.timeout_seconds = timeout_seconds

    def load(self) -> ModelCatalogResult:
        if not self.url.strip():
            return ModelCatalogResult(models=[], warnings=[])

        cache_loader = UserModelCatalogLoader(self.cache_path)
        try:
            body = self._fetch(self.url)
        except Exception as exc:  # noqa: BLE001 - any fetch failure falls back to cache
            cached = cache_loader.load()
            warning = ModelCatalogWarning(
                code="model_catalog_fetch_failed",
                message=(
                    f"Could not fetch the model catalog manifest ({exc}). "
                    + (
                        "Using the last cached copy."
                        if cached.models
                        else "No cached copy is available yet."
                    )
                ),
                source=self.url,
            )
            return ModelCatalogResult(models=cached.models, warnings=[warning, *cached.warnings])

        try:
            self._write_cache(body)
        except OSError:
            pass  # A failed cache write is non-fatal; we still parse the fresh body below.

        return cache_loader.load()

    def save(self, models: list[LocalModelDefinition]) -> None:
        # Persist to the local cache only; the remote manifest is read-only.
        UserModelCatalogLoader(self.cache_path).save(models)

    def _write_cache(self, body: str) -> None:
        path = Path(self.cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(body, encoding="utf-8")
        temporary_path.replace(path)

    def _fetch(self, url: str) -> str:
        import httpx  # Imported lazily so the module loads even without httpx.

        response = httpx.get(url, timeout=self.timeout_seconds, follow_redirects=True)
        response.raise_for_status()
        return response.text
