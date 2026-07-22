"""Choosing which file to download from a Hugging Face GGUF repository.

A repository that publishes one model usually publishes fifteen files of it, at
different quantizations — different trade-offs between size and answer quality —
plus several files that are not the model at all: vocabulary-only stubs,
multimodal projectors, shards of a split model, and builds for hardware this app
cannot use.

Until now this lived inside an HTTP route, which had two consequences. It could
not be tested without a network, and it could not explain itself: when it failed
to find a usable file it could only raise, so the interface ended up carrying
the rule as advice to the reader — *"avoid repos tagged npu/mobilint or
vocab-only files"*. Asking a person to memorise our failure modes is not a user
interface. The knowledge belongs here, where it can be applied and checked.

Everything is pure: filenames in, decisions out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Best size/quality compromise first. Q4_K_M is what most people should run on a
# laptop and what the bundled catalog uses; the rest are fallbacks for repos that
# do not publish it.
QUANT_PREFERENCE: tuple[str, ...] = (
    "q4_k_m",
    "q4_k_s",
    "q5_k_m",
    "q4_0",
    "q5_k_s",
    "q8_0",
    "q6_k",
)

# Files that are not a model we can run, and why each one is here:
#
# - vocab / tokenizer: a stub, no weights.
# - mmproj: the vision half of a multimodal model, useless on its own.
# - "-of-": one shard of a split model; the downloader fetches a single file.
# - npu / mobilint / rknn / hexagon: builds for accelerators llama.cpp cannot
#   load. These used to reach the user as a warning to avoid them by hand.
_NOT_A_RUNNABLE_MODEL = (
    "vocab",
    "tokenizer",
    "mmproj",
    "-of-",
    "npu",
    "mobilint",
    "rknn",
    "hexagon",
)

# The quantization tag inside a filename: Qwen3-8B-Q4_K_M.gguf → Q4_K_M.
# `i?q` covers both families — Q4_K_M and the newer IQ3_XXS. Written as `iq?`
# first time round, which requires a leading "i" and therefore matched neither.
_QUANT_TAG = re.compile(r"[.\-_](i?q\d+(?:_[a-z0-9]+)*|f16|f32|bf16)\.gguf$", re.IGNORECASE)

# What the trade-off means, said once, in words a person can act on. Keyed by the
# leading digit group because the family (K_M, K_S, 0) matters far less to the
# decision than the bit width.
_TRADE_OFF: dict[str, str] = {
    "2": "Smallest and fastest. Noticeably worse answers — a last resort on a small machine.",
    "3": "Small and fast, with some loss of answer quality.",
    "4": "The usual choice: good answers, modest memory.",
    "5": "Slightly better answers than the usual choice, slightly more memory.",
    "6": "Better answers, meaningfully more memory.",
    "8": "Near-original quality, about twice the memory of the usual choice.",
}
_FULL_PRECISION = (
    "The original, unquantized weights. Best quality, far more memory than most laptops have."
)


@dataclass(frozen=True)
class GgufCandidate:
    """One downloadable file, with enough context to choose between them."""

    filename: str
    quantization: str
    trade_off: str
    size_bytes: int = 0
    recommended: bool = False


def is_runnable_model_file(filename: str) -> bool:
    """False for files that are not a model this app can load and run."""
    name = (filename or "").lower()
    if not name.endswith(".gguf"):
        return False
    return not any(marker in name for marker in _NOT_A_RUNNABLE_MODEL)


def quantization_of(filename: str) -> str:
    """The quantization tag in a filename, uppercased, or "" if it has none."""
    match = _QUANT_TAG.search(filename or "")
    return match.group(1).upper() if match else ""


def describe_quantization(quantization: str) -> str:
    """What choosing this quantization costs and buys, in one sentence."""
    tag = (quantization or "").lower()
    if not tag:
        return ""
    if tag in ("f16", "f32", "bf16"):
        return _FULL_PRECISION
    digits = re.search(r"\d+", tag)
    return _TRADE_OFF.get(digits.group(0)[0], "") if digits else ""


def _preference_rank(filename: str) -> int:
    lowered = filename.lower()
    for index, quant in enumerate(QUANT_PREFERENCE):
        if quant in lowered:
            return index
    return len(QUANT_PREFERENCE)


def rank_candidates(
    files: list[str] | list[tuple[str, int]],
    *,
    preferred_quantization: str = "",
) -> list[GgufCandidate]:
    """Every usable file in a repository, best default first.

    ``files`` may be plain names or ``(name, size_bytes)`` pairs — Hugging Face
    only reports sizes when asked for them, and a missing size must not stop a
    person from choosing.

    Exactly one candidate is marked ``recommended``: the one this app would pick
    on its own. Showing the list *and* the recommendation is the point — the
    previous version picked silently, which is fine until it picks wrong and the
    person has no way to see there was a choice.
    """
    pairs = [(f, 0) if isinstance(f, str) else f for f in files or []]
    usable = [(name, size) for name, size in pairs if is_runnable_model_file(name)]
    if not usable:
        return []

    wanted = (preferred_quantization or "").strip().lower()
    if wanted:
        exact = [(name, size) for name, size in usable if wanted in name.lower()]
        usable = exact or usable

    usable.sort(key=lambda pair: (_preference_rank(pair[0]), pair[0].lower()))
    return [
        GgufCandidate(
            filename=name,
            quantization=quantization_of(name),
            trade_off=describe_quantization(quantization_of(name)),
            size_bytes=size,
            recommended=(index == 0),
        )
        for index, (name, size) in enumerate(usable)
    ]


def choose_gguf_file(files: list[str], preferred_quantization: str = "") -> str:
    """The single file to download when nobody is choosing. "" if none fits."""
    candidates = rank_candidates(files, preferred_quantization=preferred_quantization)
    return candidates[0].filename if candidates else ""


def unusable_reason(files: list[str]) -> str:
    """Why a repository yielded nothing, in terms of what the person can do.

    Distinguishing "there are no GGUF files here at all" from "the GGUF files
    here are not runnable models" matters: the first means wrong repository, the
    second means right model, wrong build. The old message guessed at both.
    """
    names = [f for f in files or [] if f]
    if not names:
        return "This repository has no files we can read."
    gguf = [f for f in names if f.lower().endswith(".gguf")]
    if not gguf:
        return (
            "This repository has no GGUF files. It is probably the original "
            "model — look for a version of it with 'GGUF' in the name."
        )
    if any("-of-" in f.lower() for f in gguf):
        return (
            "This model is split across several files, which this app cannot "
            "load yet. Look for a single-file version."
        )
    return (
        "The GGUF files here are not runnable models — they are vocabulary "
        "stubs, projectors, or builds for hardware this app does not use."
    )
