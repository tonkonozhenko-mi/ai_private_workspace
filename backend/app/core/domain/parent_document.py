"""Parent-document (small-to-big) expansion.

We retrieve on small chunks (precise matching) but hand the model larger, coherent
spans (enough surrounding context to reason). A retrieved chunk is grown with its
immediate neighbours in the same file — for code this restores the signature and
imports around a matched function body, a common source of hallucinations.

Pure and deterministic: given the same results and the same neighbour lookup it
always produces the same expansion. It never fails the answer — if a file's chunks
can't be fetched, the original retrieved chunk is kept unchanged.
"""

from collections.abc import Callable
from dataclasses import replace

from app.core.domain.chunking import strip_contextual_header
from app.core.domain.indexing import ContextSearchResult, SourceChunk

# Per-span cap so one expansion can't dominate the context window. The real
# allocation happens later in fit_context_results; this only bounds a single span.
DEFAULT_PARENT_MAX_CHARS = 4000


def expand_to_parents(
    results: list[ContextSearchResult],
    fetch_source_chunks: Callable[[str], list[SourceChunk]],
    radius: int = 1,
    max_chars: int = DEFAULT_PARENT_MAX_CHARS,
) -> list[ContextSearchResult]:
    """Expand each retrieved chunk with its ±``radius`` neighbours in the same file.

    ``fetch_source_chunks`` maps a ``source_path`` to that file's chunks, ordered
    by chunk_index (typically ``vector_store.get_source_chunks`` bound to a
    workspace). Overlapping expansions within a file merge into one contiguous span
    (dedup by file). The result order follows the input's score-desc ordering; a
    merged span takes the highest score among the chunks that seeded it.

    Fail-open per file: if a file's chunks come back empty, or a retrieved chunk
    can't be located among them, that result is returned unchanged.
    """
    if not results:
        return []
    if radius < 0:
        radius = 0

    # Cache per-file lookups so we fetch each file at most once.
    file_cache: dict[str, list[SourceChunk]] = {}

    def chunks_for(path: str) -> list[SourceChunk]:
        if path not in file_cache:
            try:
                file_cache[path] = list(fetch_source_chunks(path) or [])
            except Exception:  # noqa: BLE001 — fail-open: expansion is optional
                file_cache[path] = []
        return file_cache[path]

    # Seed set per file: chunk_index → best (score, order, result) that reached it.
    # ``order`` is the chunk's position in the incoming (already ranked) list, used
    # only as a deterministic tie-break — never as a score.
    seeds_by_file: dict[str, dict[int, tuple[float, int, ContextSearchResult]]] = {}
    # Results we can't expand (unknown file / chunk) pass through unchanged, keeping
    # their original position.
    passthrough: list[tuple[int, ContextSearchResult]] = []

    for order, result in enumerate(results):
        source_chunks = chunks_for(result.source_path)
        index_by_id = {chunk.chunk_id: chunk.chunk_index for chunk in source_chunks}
        seed_index = index_by_id.get(result.chunk_id)
        if seed_index is None:
            passthrough.append((order, result))
            continue
        bucket = seeds_by_file.setdefault(result.source_path, {})
        existing = bucket.get(seed_index)
        if existing is None or result.score > existing[0]:
            bucket[seed_index] = (result.score, order, result)

    # Build merged spans per file, then flatten with a deterministic ordering.
    spans: list[tuple[float, int, ContextSearchResult]] = []
    for source_path, seeds in seeds_by_file.items():
        source_chunks = chunks_for(source_path)
        by_index = {chunk.chunk_index: chunk for chunk in source_chunks}
        available = sorted(by_index)
        for span_indices, seed, seed_index in _merge_spans(seeds, available, radius):
            score, order, _ = seed
            spans.append(
                (score, order, _build_span(span_indices, by_index, seed, seed_index, max_chars))
            )

    # Score desc; ties broken by original order so output is fully deterministic.
    spans.sort(key=lambda item: (-item[0], item[1]))
    passthrough.sort(key=lambda item: item[0])

    # Interleave spans (ranked) ahead of pure pass-throughs but keep pass-throughs
    # in their original relative order at the tail — they had no expansion signal to
    # re-rank on, and were already ranked upstream.
    ordered = [result for _, _, result in spans]
    ordered.extend(result for _, result in passthrough)
    return ordered


def _merge_spans(
    seeds: dict[int, tuple[float, int, ContextSearchResult]],
    available: list[int],
    radius: int,
) -> list[tuple[list[int], tuple[float, int, ContextSearchResult], int]]:
    """Group seed indices into contiguous spans covering each seed ±radius.

    Returns, per span, the ordered list of chunk indices it spans, the seed
    (score, order, result) with the highest score inside it, and that winning seed's
    chunk index. The winning seed supplies the span's score, metadata and citation.
    """
    if not available:
        return []
    position = {index: pos for pos, index in enumerate(available)}

    # Each seed covers a window of neighbours by position (not raw index, so gaps in
    # the index sequence don't over-reach). Collect covered positions with the seed
    # that produced them, then merge overlapping windows.
    windows: list[tuple[int, int, tuple[float, int, ContextSearchResult], int]] = []
    for seed_index, seed in sorted(seeds.items()):
        pos = position.get(seed_index)
        if pos is None:
            continue
        lo = max(0, pos - radius)
        hi = min(len(available) - 1, pos + radius)
        windows.append((lo, hi, seed, seed_index))

    windows.sort(key=lambda item: item[0])
    merged: list[tuple[int, int, tuple[float, int, ContextSearchResult], int]] = []
    for lo, hi, seed, seed_index in windows:
        if merged and lo <= merged[-1][1] + 1:
            prev_lo, prev_hi, prev_seed, prev_index = merged[-1]
            if seed[0] > prev_seed[0]:
                best_seed, best_index = seed, seed_index
            else:
                best_seed, best_index = prev_seed, prev_index
            merged[-1] = (prev_lo, max(prev_hi, hi), best_seed, best_index)
        else:
            merged.append((lo, hi, seed, seed_index))

    return [
        ([available[p] for p in range(lo, hi + 1)], seed, seed_index)
        for lo, hi, seed, seed_index in merged
    ]


def _build_span(
    span_indices: list[int],
    by_index: dict[int, SourceChunk],
    seed: tuple[float, int, ContextSearchResult],
    seed_index: int,
    max_chars: int,
) -> ContextSearchResult:
    """Join a span's chunks into one ContextSearchResult.

    The seed chunk is always included; neighbours are added outward (closest first)
    while the joined content stays within ``max_chars``. Chunks are then emitted in
    file order — the first kept chunk keeps its contextual header (provenance /
    citation), the rest are header-stripped so the body reads continuously.
    """
    score, _, seed_result = seed
    if seed_index not in by_index:
        return seed_result

    kept = {seed_index}
    total = len(by_index[seed_index].content)
    # Walk neighbours in order of distance from the seed so growth is symmetric and
    # the closest context is preferred when the budget is tight.
    for index in sorted(
        (i for i in span_indices if i != seed_index),
        key=lambda i: (abs(i - seed_index), i),
    ):
        chunk = by_index.get(index)
        if chunk is None:
            continue
        addition = len(strip_contextual_header(chunk.content))
        if total + addition > max_chars:
            continue
        kept.add(index)
        total += addition

    ordered_indices = sorted(kept)
    pieces: list[str] = []
    for position, index in enumerate(ordered_indices):
        chunk = by_index[index]
        pieces.append(chunk.content if position == 0 else strip_contextual_header(chunk.content))

    content = "\n\n".join(pieces)
    first_chunk = by_index[ordered_indices[0]]
    return replace(seed_result, chunk_id=first_chunk.chunk_id, content=content, score=score)
