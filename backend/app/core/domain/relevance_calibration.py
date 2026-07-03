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
similarity (queries are short, chunks long; some embedders are asymmetric), so the
floor is a *calibrated relative* threshold, not a physical constant — still far more
transferable across models than a single hardcoded number.
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
