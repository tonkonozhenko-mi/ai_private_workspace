"""Read a GGUF file's own description of itself: layers, heads, context length.

A GGUF begins with a key/value header — the model telling us what it is — and
then gigabytes of weights we have no interest in. We read only the header, and
only the four or five keys that decide how much memory one token of context
costs. That is what lets the app size the window to the machine instead of
guessing a number and hoping.

Deliberately tolerant: a file we cannot parse yields ``None``, and the caller
falls back to an estimate. A model that will not describe itself should cost us a
smaller window, not a crash.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

_MAGIC = b"GGUF"
# The header is small; refuse to read a pathological one rather than stream a file.
_MAX_HEADER_BYTES = 8 * 1024 * 1024

# GGUF value type ids (llama.cpp: enum gguf_type).
_UINT8, _INT8, _UINT16, _INT16, _UINT32, _INT32, _FLOAT32 = range(7)
_BOOL, _STRING, _ARRAY, _UINT64, _INT64, _FLOAT64 = range(7, 13)

_FIXED: dict[int, tuple[str, int]] = {
    _UINT8: ("<B", 1),
    _INT8: ("<b", 1),
    _UINT16: ("<H", 2),
    _INT16: ("<h", 2),
    _UINT32: ("<I", 4),
    _INT32: ("<i", 4),
    _FLOAT32: ("<f", 4),
    _BOOL: ("<?", 1),
    _UINT64: ("<Q", 8),
    _INT64: ("<q", 8),
    _FLOAT64: ("<d", 8),
}

# The architecture prefixes its own keys ("llama.block_count", "qwen2.block_count"),
# so we match on the suffix and take whichever architecture the file happens to be.
_WANTED_SUFFIXES = (
    ".context_length",
    ".block_count",
    ".embedding_length",
    ".attention.head_count",
    ".attention.head_count_kv",
)


@dataclass(frozen=True)
class GgufArchitecture:
    """What a GGUF says about its own shape. Any field may be missing."""

    context_length: int | None = None
    block_count: int | None = None
    embedding_length: int | None = None
    head_count: int | None = None
    head_count_kv: int | None = None


class _Reader:
    def __init__(self, handle) -> None:
        self._handle = handle

    def take(self, count: int) -> bytes:
        data = self._handle.read(count)
        if len(data) != count:
            raise ValueError("GGUF header ended early")
        return data

    def scalar(self, type_id: int):
        fmt, size = _FIXED[type_id]
        return struct.unpack(fmt, self.take(size))[0]

    def string(self) -> str:
        length = self.scalar(_UINT64)
        if length > _MAX_HEADER_BYTES:
            raise ValueError("GGUF string is implausibly long")
        return self.take(length).decode("utf-8", "replace")

    def value(self, type_id: int):
        """Read one value, discarding what we cannot use — we must still consume
        it exactly, or every key after it would be read from the wrong offset."""
        if type_id in _FIXED:
            return self.scalar(type_id)
        if type_id == _STRING:
            return self.string()
        if type_id == _ARRAY:
            element_type = self.scalar(_UINT32)
            count = self.scalar(_UINT64)
            if count > _MAX_HEADER_BYTES:
                raise ValueError("GGUF array is implausibly long")
            for _ in range(count):
                self.value(element_type)
            return None
        raise ValueError(f"Unknown GGUF value type {type_id}")


def read_gguf_architecture(path: str | Path) -> GgufArchitecture | None:
    """The shape of the model in ``path``, or ``None`` if the file won't say."""
    try:
        with Path(path).open("rb") as handle:
            reader = _Reader(handle)
            if reader.take(4) != _MAGIC:
                return None
            reader.scalar(_UINT32)  # format version
            reader.scalar(_UINT64)  # tensor count — the weights, not our business
            kv_count = reader.scalar(_UINT64)
            found: dict[str, int] = {}
            for _ in range(kv_count):
                key = reader.string()
                value = reader.value(reader.scalar(_UINT32))
                if isinstance(value, int) and not isinstance(value, bool):
                    for suffix in _WANTED_SUFFIXES:
                        if key.endswith(suffix):
                            found.setdefault(suffix, value)
                if len(found) == len(_WANTED_SUFFIXES):
                    break
    except (OSError, ValueError, struct.error):
        return None
    if not found:
        return None
    return GgufArchitecture(
        context_length=found.get(".context_length"),
        block_count=found.get(".block_count"),
        embedding_length=found.get(".embedding_length"),
        head_count=found.get(".attention.head_count"),
        head_count_kv=found.get(".attention.head_count_kv"),
    )
