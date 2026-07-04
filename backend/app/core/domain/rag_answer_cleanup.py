"""Deterministic clean-up of RAG answers before they're shown/stored.

Small local models (e.g. Mistral-7B) often end an answer by echoing the prompt's
per-chunk provenance headers as a list — nine identical lines like
``1. source_path: .agents/skills/…/SKILL.md``. The app already renders a proper
"N sources from your project" block, so this trailing echo is pure noise.

We strip only the *trailing* contiguous block of ``source_path:`` lines (plus an
optional ``Sources:`` header just above it). Inline mentions inside a sentence are
left alone — those read naturally and, if anything, need a prompt fix, not a
risky body edit. Nothing here touches the grounding check, which reads
backtick-quoted file tokens rather than these labels. Pure and deterministic.
"""

from __future__ import annotations

import re

# A line that is (only) a provenance echo: optional list marker / bullet / quote,
# then "source_path:". Matches "1. source_path: x", "- source_path: x",
# "(source_path: x)", "`source_path: x`".
_SOURCE_PATH_LINE = re.compile(
    r"^\s*[-*]?\s*(?:\d+[.)]\s*)?[`(\[]?\s*source_path\s*:", re.IGNORECASE
)
# A standalone "Sources:" / "Source" header line above such a block.
_SOURCES_HEADER = re.compile(r"^\s*[`*_]*\s*sources?\s*:?\s*[`*_]*\s*$", re.IGNORECASE)


def strip_source_path_echo(text: str) -> str:
    """Remove a trailing ``source_path:`` echo block (and its optional header).

    Returns the text unchanged if there's no such trailing block, or if stripping
    it would leave nothing (never blank an answer).
    """
    if not text or "source_path" not in text.lower():
        return text

    lines = text.rstrip("\n").split("\n")
    # Walk up from the end over a contiguous run of blank / source_path lines.
    i = len(lines) - 1
    saw_source_path = False
    while i >= 0:
        stripped = lines[i].strip()
        if stripped == "":
            i -= 1
            continue
        if _SOURCE_PATH_LINE.match(lines[i]):
            saw_source_path = True
            i -= 1
            continue
        break

    if not saw_source_path:
        return text

    keep_end = i + 1
    # Drop a "Sources:" header immediately above the block, if present.
    if keep_end - 1 >= 0 and _SOURCES_HEADER.match(lines[keep_end - 1]):
        keep_end -= 1

    cleaned = "\n".join(lines[:keep_end]).rstrip()
    # Never blank the whole answer (e.g. a reply that was ONLY a source list).
    return cleaned if cleaned else text
