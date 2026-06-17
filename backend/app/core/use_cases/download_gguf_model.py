"""Resolve a GGUF model (catalog entry or custom HF repo/file) and download it.

This is the llama.cpp counterpart to the Ollama pull job: it downloads model
*data* into the app data dir. The architecture-specific ``llama-server`` binary
is bundled with the app and never downloaded here.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.domain.gguf_catalog import (
    HUGGINGFACE_BASE_URL,
    GgufModel,
    find_gguf_model,
)
from app.core.ports.gguf_downloader import GgufDownloaderPort

# A GGUF that exists but is far smaller than expected is almost certainly a
# half-written or error page; treat anything under this as "not installed".
_MIN_VALID_BYTES = 1_000_000


@dataclass(frozen=True)
class GgufModelRef:
    """Either a catalog id, or an explicit Hugging Face repo + filename."""

    model_id: str | None = None
    repo_id: str | None = None
    filename: str | None = None


class GgufModelNotResolvedError(ValueError):
    pass


def resolve_gguf_model(ref: GgufModelRef) -> GgufModel:
    if ref.model_id:
        model = find_gguf_model(ref.model_id)
        if model is not None:
            return model
    if ref.repo_id and ref.filename:
        # Custom model pasted by an advanced user: build a one-off entry.
        return GgufModel(
            id=f"{ref.repo_id}/{ref.filename}",
            name=ref.filename,
            model_type="llm",
            repo_id=ref.repo_id,
            filename=ref.filename,
            quantization="custom",
            size_bytes=0,
        )
    raise GgufModelNotResolvedError(
        "Provide a known model id, or a Hugging Face repo_id and filename."
    )


class DownloadGgufModelUseCase:
    def __init__(self, downloader: GgufDownloaderPort, app_data_dir: str | Path) -> None:
        self.downloader = downloader
        self.app_data_dir = Path(app_data_dir)

    def destination_path(self, model: GgufModel) -> Path:
        return self.app_data_dir / model.relative_storage_path

    def is_installed(self, model: GgufModel) -> bool:
        path = self.destination_path(model)
        try:
            return path.is_file() and path.stat().st_size >= _MIN_VALID_BYTES
        except OSError:
            return False

    def execute(
        self,
        ref: GgufModelRef,
        progress_callback: Callable[[int, int | None], None] | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> str:
        model = resolve_gguf_model(ref)
        destination = self.destination_path(model)
        if self.is_installed(model):
            return str(destination)
        url = (
            model.download_url
            if model.repo_id in model.download_url
            else f"{HUGGINGFACE_BASE_URL}/{model.repo_id}/resolve/main/{model.filename}"
        )
        return self.downloader.download(
            url=url,
            destination_path=str(destination),
            expected_size_bytes=model.size_bytes or None,
            progress_callback=progress_callback,
            cancellation_check=cancellation_check,
        )
