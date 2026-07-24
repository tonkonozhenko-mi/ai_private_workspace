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


def _split_custom_model_id(model_id: str) -> tuple[str, str] | None:
    """A custom model's id is ``f"{repo_id}/{filename}"`` (see below), e.g.
    ``unsloth/Qwen3-0.6B-GGUF/Qwen3-0.6B-Q4_K_M.gguf``. Split it back into
    (repo_id, filename) so a custom model referenced by id alone can be
    re-resolved — the workspace selection stores only this one string, and the
    engine-start path passes it as ``model_id``. Without this, a custom answer
    model chosen in a workspace could not be resolved on re-activation (it is not
    in the static catalog), so ``set_llm_ref`` silently failed and the engine
    fell back to the recommended default. The filename is the last path segment
    and always ends in ``.gguf``; the repo_id ("owner/name") is everything before
    it. Catalog ids ("qwen3-4b", "qwen2.5-coder:7b") never end in ``.gguf``, so
    this cannot mistake one for a custom model.
    """
    stripped = (model_id or "").strip()
    if "/" not in stripped or not stripped.lower().endswith(".gguf"):
        return None
    repo_id, _, filename = stripped.rpartition("/")
    if not repo_id or not filename:
        return None
    return repo_id, filename


def resolve_gguf_model(ref: GgufModelRef) -> GgufModel:
    repo_id = ref.repo_id
    filename = ref.filename
    if ref.model_id:
        model = find_gguf_model(ref.model_id)
        if model is not None:
            return model
        # Not a catalog id — it may be a custom model's composite id. Recover the
        # repo/file so the one-off entry below can rebuild it (unless an explicit
        # repo_id/filename was already given, which wins).
        if not (repo_id and filename):
            split = _split_custom_model_id(ref.model_id)
            if split is not None:
                repo_id, filename = split
    if repo_id and filename:
        # Custom model (pasted, searched by name, or persisted per-workspace):
        # build a one-off entry.
        return GgufModel(
            id=f"{repo_id}/{filename}",
            name=filename,
            model_type="llm",
            repo_id=repo_id,
            filename=filename,
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

    def delete(self, model: GgufModel) -> bool:
        """Remove a downloaded GGUF file from disk. Returns True if a file was
        deleted. Only model data is touched — never project files."""
        path = self.destination_path(model)
        try:
            if path.is_file():
                path.unlink()
                return True
        except OSError:
            pass
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
