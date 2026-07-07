"""Calibrate the retrieval abstention threshold to an embedding model's own scale.

Cosine-similarity scores are not comparable across embedding models: for some, two
unrelated snippets sit around 0.1; for others, around 0.5. A single hardcoded
abstention threshold (``0.38``) therefore misfires whenever the model changes — too
high yields false "not in the project", too low answers confidently from noise.

The fix is to measure the model's *noise floor* directly instead of guessing it.
During indexing we sample random chunk pairs — which are, on average, unrelated —
and look at how similar the model thinks they are. The p95 of that background
distribution plus a small margin is a score a genuinely relevant match should clear.
No labels and no LLM are involved, and it recalibrates automatically whenever the
embedder changes, which is exactly the property a fixed constant lacks.

Everything here is pure (stdlib only) so it can be unit-tested without a model.

Caveat worth remembering: chunk↔chunk similarity is not identical to query↔chunk
similarity (queries are short, chunks long; some embedders are asymmetric), and in a
topically-focused repo random chunk pairs are NOT truly unrelated (they share the
project's vocabulary), so the sampled background can sit *above* real query↔chunk
match scores. That would wrongly abstain on on-topic questions. Because of this the
calibrated floor is treated by consumers as a **permissive-only** signal: it may
lower the abstention bar for embedders whose matches score low, but is capped at the
historic default so it can't raise the bar above a value known not to over-abstain
(see ``AskWorkspaceQuestionUseCase._relevance_threshold``).
"""

from __future__ import annotations

import math
import random

# Keep the calibrated floor inside a sane band, so a degenerate sample (a tiny index,
# or near-duplicate chunks that inflate the background) can't push abstention to a
# useless extreme in either direction.
MIN_FLOOR = 0.15
MAX_FLOOR = 0.60

# Below this many sampled pairs the p95 is too noisy to trust; keep the caller's
# fallback (the hardcoded default) instead of persisting a shaky floor.
MIN_SAMPLES = 30

DEFAULT_MAX_PAIRS = 200
DEFAULT_PERCENTILE = 0.95
DEFAULT_MARGIN = 0.05

# A fixed, deliberately banal set of non-project "probe" queries. Their highest
# similarity to a corpus is an empirical ceiling for how high genuinely off-topic
# chit-chat scores against THIS (embedder, corpus) pair. Unlike the chunk↔chunk
# floor, this ceiling is measured on the query↔chunk scale the abstention decision
# actually uses, which is why it transfers between corpora where a fixed floor
# margin does not. Keep every entry short, generic and domain-neutral so it can
# never accidentally resemble a real project's content (they must stay non-project
# for ANY domain — infra, web, ML, finance …).
PROBE_QUERIES: tuple[str, ...] = (
    "hello how are you today",
    "what time is it right now",
    "what is the weather like today",
    "what is the capital of France",
    "what is two plus two",
    "tell me a fun fact",
    "how do I make pancakes",
    "recommend a good movie to watch",
)

# Scan at most this many corpus chunks per probe. The ceiling is a maximum, so a
# sample can only ever underestimate it (which merely lowers the threshold a touch —
# safe under the min() combination). The cap keeps a very large index bounded to a
# few milliseconds; small, homogeneous corpora (where the ceiling matters most) are
# scanned in full.
DEFAULT_PROBE_MAX_CHUNKS = 4000


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 if either is a zero vector."""
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile (``q`` in ``[0, 1]``), matching numpy's default.

    Pure so it can stand in for numpy in the domain layer and be tested exactly.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[int(pos)]
    frac = pos - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def sample_pair_cosines(
    embeddings: list[list[float]],
    *,
    max_pairs: int = DEFAULT_MAX_PAIRS,
    seed: int = 0,
) -> list[float]:
    """Cosine similarities of up to ``max_pairs`` random *distinct* chunk pairs.

    This is the model's background ("unrelated") similarity distribution for this
    corpus. Deterministic given ``seed`` so calibration is reproducible. Attempts are
    bounded so a tiny index can never loop forever hunting for unseen pairs.
    """
    n = len(embeddings)
    if n < 2:
        return []
    rng = random.Random(seed)
    target = min(max_pairs, n * (n - 1) // 2)
    seen: set[tuple[int, int]] = set()
    cosines: list[float] = []
    max_attempts = target * 20
    attempts = 0
    while len(cosines) < target and attempts < max_attempts:
        attempts += 1
        i = rng.randrange(n)
        j = rng.randrange(n)
        if i == j:
            continue
        key = (i, j) if i < j else (j, i)
        if key in seen:
            continue
        seen.add(key)
        cosines.append(cosine(embeddings[i], embeddings[j]))
    return cosines


def calibrate_relevance_floor(
    pair_cosines: list[float],
    *,
    percentile_q: float = DEFAULT_PERCENTILE,
    margin: float = DEFAULT_MARGIN,
    min_floor: float = MIN_FLOOR,
    max_floor: float = MAX_FLOOR,
    min_samples: int = MIN_SAMPLES,
) -> float | None:
    """Return a calibrated abstention floor from a background-cosine sample.

    ``None`` means "not enough signal to trust" — the caller should keep its fallback
    (the hardcoded default, or a previously-calibrated floor) rather than overwrite it
    with a shaky value. Otherwise the floor is ``p95 + margin``, clamped to a sane band.
    """
    if len(pair_cosines) < min_samples:
        return None
    floor = percentile(pair_cosines, percentile_q) + margin
    return max(min_floor, min(max_floor, floor))


def calibrate_from_embeddings(
    embeddings: list[list[float]],
    *,
    max_pairs: int = DEFAULT_MAX_PAIRS,
    seed: int = 0,
    **kwargs: float,
) -> float | None:
    """Convenience: sample random pairs from ``embeddings`` and calibrate a floor.

    Returns ``None`` when the index is too small to sample a trustworthy background.
    """
    cosines = sample_pair_cosines(embeddings, max_pairs=max_pairs, seed=seed)
    return calibrate_relevance_floor(cosines, **kwargs)


def _sample_chunks(
    embeddings: list[list[float]], *, max_chunks: int, seed: int
) -> list[list[float]]:
    """A deterministic subset of chunk embeddings, capped at ``max_chunks``.

    Returns the whole list when it already fits, so small corpora — where the probe
    ceiling matters most — are scanned in full.
    """
    if len(embeddings) <= max_chunks:
        return embeddings
    rng = random.Random(seed)
    return [embeddings[i] for i in rng.sample(range(len(embeddings)), max_chunks)]


def probe_ceiling(
    probe_embeddings: list[list[float]],
    chunk_embeddings: list[list[float]],
    *,
    max_chunks: int = DEFAULT_PROBE_MAX_CHUNKS,
    seed: int = 0,
) -> float | None:
    """Highest similarity any neutral probe query reaches against the corpus.

    This is the empirical ceiling for off-topic chit-chat against this
    ``(embedder, corpus)`` pair, measured on the query↔chunk scale. ``None`` when
    either side is empty (no probes embedded, or an empty index). Scans a bounded,
    deterministic sample of chunks (the whole corpus when small); being a maximum, a
    sample can only underestimate the ceiling, which is safe under the consumer's
    ``min()`` combination (it can only lower the abstention bar, never raise it).
    """
    if not probe_embeddings or not chunk_embeddings:
        return None
    sample = _sample_chunks(chunk_embeddings, max_chunks=max_chunks, seed=seed)
    best: float | None = None
    for probe in probe_embeddings:
        for chunk in sample:
            score = cosine(probe, chunk)
            if best is None or score > best:
                best = score
    return best
