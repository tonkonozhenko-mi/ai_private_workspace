"""Noise-floor calibration of the retrieval abstention threshold (pure domain)."""

import math

from app.core.domain.relevance_calibration import (
    MAX_FLOOR,
    MIN_FLOOR,
    calibrate_from_embeddings,
    calibrate_relevance_floor,
    cosine,
    percentile,
    sample_pair_cosines,
)


def test_cosine_basic():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert abs(cosine([1.0, 1.0], [1.0, 0.0]) - (1 / math.sqrt(2))) < 1e-9


def test_cosine_zero_vector_is_zero_not_error():
    assert cosine([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_percentile_matches_numpy_linear():
    values = [0.0, 1.0, 2.0, 3.0, 4.0]
    # numpy.percentile(values, 95, method="linear") == 3.8
    assert abs(percentile(values, 0.95) - 3.8) < 1e-9
    assert percentile(values, 0.0) == 0.0
    assert percentile(values, 1.0) == 4.0
    assert percentile([7.0], 0.95) == 7.0
    assert percentile([], 0.5) == 0.0


def test_sample_pairs_are_distinct_and_bounded():
    embeddings = [[float(i), float(i + 1)] for i in range(10)]
    cosines = sample_pair_cosines(embeddings, max_pairs=5, seed=1)
    assert len(cosines) == 5
    # Deterministic given the seed
    again = sample_pair_cosines(embeddings, max_pairs=5, seed=1)
    assert cosines == again


def test_sample_pairs_caps_at_available_combinations():
    # 3 vectors → only 3 distinct pairs exist, even if we ask for 200.
    embeddings = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    cosines = sample_pair_cosines(embeddings, max_pairs=200, seed=0)
    assert len(cosines) == 3


def test_sample_pairs_needs_two_vectors():
    assert sample_pair_cosines([[1.0, 2.0]], max_pairs=10) == []
    assert sample_pair_cosines([], max_pairs=10) == []


def test_calibrate_returns_none_below_min_samples():
    # A handful of pairs is too noisy to trust — keep the caller's fallback.
    assert calibrate_relevance_floor([0.1, 0.2, 0.3]) is None


def test_calibrate_is_p95_plus_margin_clamped():
    # Background clustered near 0.1 → floor a little above it.
    cosines = [0.1] * 100
    floor = calibrate_relevance_floor(cosines, margin=0.05)
    assert floor is not None
    assert abs(floor - 0.15) < 1e-9


def test_calibrate_clamps_high_background_to_max():
    cosines = [0.95] * 100
    floor = calibrate_relevance_floor(cosines, margin=0.05)
    assert floor == MAX_FLOOR


def test_calibrate_clamps_low_background_to_min():
    cosines = [-0.5] * 100
    floor = calibrate_relevance_floor(cosines, margin=0.0)
    assert floor == MIN_FLOOR


def test_different_scales_yield_different_floors():
    # The whole point: a model whose "unrelated" pairs sit higher gets a higher floor.
    low_model = calibrate_relevance_floor([0.1] * 100)
    high_model = calibrate_relevance_floor([0.45] * 100)
    assert low_model is not None and high_model is not None
    assert high_model > low_model


def test_calibrate_from_embeddings_small_index_is_none():
    embeddings = [[1.0, 0.0], [0.0, 1.0]]  # only 1 pair < MIN_SAMPLES
    assert calibrate_from_embeddings(embeddings) is None


def test_calibrate_from_embeddings_returns_value_on_real_index():
    # 60 varied vectors → enough distinct pairs to calibrate.
    embeddings = [[math.cos(i), math.sin(i), float(i % 3)] for i in range(60)]
    floor = calibrate_from_embeddings(embeddings, seed=7)
    assert floor is not None
    assert MIN_FLOOR <= floor <= MAX_FLOOR
