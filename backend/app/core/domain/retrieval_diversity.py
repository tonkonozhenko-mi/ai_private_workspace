"""Keep retrieved context diverse across files.

MMR de-duplicates by *embedding* similarity, but several chunks of one big file
can each be distinct enough to survive it — so a single dominant file can fill the
whole context and starve genuinely relevant files (observed live: all 5 sources
were the same SKILL.md while the Terraform files that answered the question were
crowded out). This caps how many chunks any one file may contribute, applied to
the candidate pool *before* selection so the final answer draws from more files.

Pure and order-preserving: higher-scored chunks come first from the store, so
keeping the first N per path keeps the best N of that file.
"""

from __future__ import annotations

from app.core.domain.indexing import ContextSearchResult

DEFAULT_MAX_PER_SOURCE = 3


def limit_per_source(
    results: list[ContextSearchResult],
    max_per_source: int = DEFAULT_MAX_PER_SOURCE,
) -> list[ContextSearchResult]:
    """Return ``results`` with at most ``max_per_source`` chunks per source_path,
    preserving order. ``max_per_source <= 0`` disables the cap."""
    if max_per_source <= 0:
        return list(results)
    counts: dict[str, int] = {}
    kept: list[ContextSearchResult] = []
    for result in results:
        path = result.source_path
        seen = counts.get(path, 0)
        if seen >= max_per_source:
            continue
        counts[path] = seen + 1
        kept.append(result)
    return kept
