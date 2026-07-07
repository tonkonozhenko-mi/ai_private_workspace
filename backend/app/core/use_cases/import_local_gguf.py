"""Register a GGUF model that already exists on the user's disk.

Instead of re-downloading a model the user already has (from LM Studio, another
llama.cpp install, or a manual download), point the app at the file and it becomes
usable like any downloaded model. The file is registered inside the managed model
directory as a symlink (so nothing large is copied); when a symlink can't be made —
some Windows setups, or a different filesystem — it falls back to copying. Either
way the existing scan, switch and delete machinery finds and manages it unchanged.

Deleting an imported model removes only the app's link/copy, never the user's
original file (deletion unlinks the managed path, which is the symlink itself).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from app.core.domain.local_gguf_import import (
    IMPORTED_REPO,
    guess_gguf_model_type,
    imported_model_id,
    imported_relative_path,
    is_gguf_filename,
    is_valid_gguf_size,
    looks_like_gguf_header,
)


class LocalGgufImportError(ValueError):
    """The chosen file can't be imported as a GGUF model (with a plain reason)."""


@dataclass(frozen=True)
class ImportedGguf:
    model_id: str
    repo_id: str
    filename: str
    model_type: str
    size_bytes: int
    stored_path: str
    linked: bool  # True when a symlink was used, False when the file was copied


class ImportLocalGgufUseCase:
    def __init__(self, app_data_dir: str | Path) -> None:
        self.app_data_dir = Path(app_data_dir)

    def execute(self, source_path: str, model_type: str | None = None) -> ImportedGguf:
        source = Path(source_path).expanduser()
        self._validate(source)

        filename = source.name
        chosen_type = model_type or guess_gguf_model_type(filename)
        destination = self.app_data_dir / imported_relative_path(filename)
        destination.parent.mkdir(parents=True, exist_ok=True)

        linked = self._place(source.resolve(), destination)
        try:
            size_bytes = destination.stat().st_size
        except OSError:
            size_bytes = source.stat().st_size

        return ImportedGguf(
            model_id=imported_model_id(filename),
            repo_id=IMPORTED_REPO,
            filename=filename,
            model_type=chosen_type,
            size_bytes=size_bytes,
            stored_path=str(destination),
            linked=linked,
        )

    def _validate(self, source: Path) -> None:
        if not source.is_file():
            raise LocalGgufImportError("No file was found at that path.")
        if not is_gguf_filename(source.name):
            raise LocalGgufImportError("That file is not a .gguf model.")
        try:
            size = source.stat().st_size
        except OSError as exc:
            raise LocalGgufImportError("The file could not be read.") from exc
        if not is_valid_gguf_size(size):
            raise LocalGgufImportError(
                "The file is too small to be a real model — it may be incomplete."
            )
        try:
            with source.open("rb") as handle:
                header = handle.read(4)
        except OSError as exc:
            raise LocalGgufImportError("The file could not be read.") from exc
        if not looks_like_gguf_header(header):
            raise LocalGgufImportError(
                "That file does not look like a GGUF model (missing its header)."
            )

    @staticmethod
    def _place(source: Path, destination: Path) -> bool:
        """Register the model at ``destination`` pointing to ``source``. Prefer a
        symlink (no large copy); fall back to copying when symlinks aren't allowed
        or the two paths are on different filesystems. Returns True if a symlink was
        used. Replaces a stale link/copy for the same filename so re-importing is
        idempotent."""
        try:
            if destination.is_symlink() or destination.exists():
                destination.unlink()
        except OSError:
            pass
        try:
            destination.symlink_to(source)
            return True
        except (OSError, NotImplementedError):
            shutil.copy2(source, destination)
            return False
