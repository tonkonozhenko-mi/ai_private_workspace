"""Pure rules for importing a GGUF model the user already has on disk.

Many people (especially the DevOps audience) already keep GGUF models locally —
downloaded through LM Studio, another llama.cpp setup, or by hand. Re-downloading
them through the app is wasteful. These helpers decide what makes a file a valid,
usable GGUF and where an imported one is registered, so the rest of the app treats
it exactly like a model it downloaded itself.

Everything here is pure: the on-disk reading, symlinking and copying live in the
use case. ``IMPORTED_REPO`` is the synthetic "repository" imported models are filed
under, so they surface in the custom-model list next to catalog downloads.
"""

from __future__ import annotations

# Every GGUF file begins with these four magic bytes. Checking them (not just the
# extension) stops a mis-named or truncated file from being registered as a model.
GGUF_MAGIC = b"GGUF"

# A real quantised model is many megabytes; anything smaller is a stub, an error
# page saved with the wrong name, or a half-copied file.
MIN_GGUF_BYTES = 1_000_000

# Synthetic repo id imported models are filed under in the managed model dir, so
# the existing custom-GGUF scan lists and manages them like any downloaded model.
IMPORTED_REPO = "local"

# Filename fragments that mark an embedding model, so an imported embedder isn't
# mistaken for an answer model. Mirrors the catalog's own heuristic.
_EMBEDDING_NAME_HINTS = ("embed", "nomic", "bge-", "bge_", "gte-", "e5-", "minilm", "mxbai")


def is_gguf_filename(name: str) -> bool:
    return name.lower().endswith(".gguf")


def looks_like_gguf_header(header: bytes) -> bool:
    """True when the leading bytes carry the GGUF magic number."""
    return header[:4] == GGUF_MAGIC


def is_valid_gguf_size(size_bytes: int) -> bool:
    return size_bytes >= MIN_GGUF_BYTES


def imported_model_id(filename: str) -> str:
    """The catalog id an imported file is exposed under (``local/<filename>``),
    matching how custom downloads are identified (``repo/filename``)."""
    return f"{IMPORTED_REPO}/{filename}"


def imported_relative_path(filename: str) -> str:
    """Where the imported model is registered inside the managed model dir, so the
    existing scan and switch/delete machinery finds it unchanged."""
    return f"models/gguf/{IMPORTED_REPO}/{filename}"


def guess_gguf_model_type(filename: str) -> str:
    """Best-effort ``embedding`` vs ``llm`` from the filename, so an imported
    embedder lands in the right place. Defaults to ``llm``."""
    lowered = filename.lower()
    return "embedding" if any(hint in lowered for hint in _EMBEDDING_NAME_HINTS) else "llm"
