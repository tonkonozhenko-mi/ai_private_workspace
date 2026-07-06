"""Ask picks the abstention threshold with the right precedence:
env override > fake-embedding constant > per-index calibrated floor > default.
"""

import os
import types

from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.use_cases.ask_workspace_question import (
    DEFAULT_RELEVANCE_THRESHOLD,
    FAKE_EMBEDDING_RELEVANCE_THRESHOLD,
    RELEVANCE_THRESHOLD_ENV_VAR,
    AskWorkspaceQuestionUseCase,
)

_threshold = AskWorkspaceQuestionUseCase._relevance_threshold


def _status(floor):
    return WorkspaceIndexStatus(
        workspace_id="w",
        status="indexed",
        indexed_files_count=1,
        chunks_count=1,
        skipped_files_count=0,
        last_indexed_at=None,
        last_error=None,
        embedding_model="m",
        relevance_floor=floor,
    )


def _real_self():
    return types.SimpleNamespace(embedding_provider=types.SimpleNamespace(provider_name="ollama"))


def _fake_self():
    return types.SimpleNamespace(embedding_provider=types.SimpleNamespace(provider_name="fake"))


def _clear_env():
    os.environ.pop(RELEVANCE_THRESHOLD_ENV_VAR, None)


def test_no_index_status_uses_default():
    _clear_env()
    assert _threshold(_real_self()) == DEFAULT_RELEVANCE_THRESHOLD


def test_threshold_sits_just_below_calibrated_floor():
    # The threshold is the calibrated noise floor minus a margin (0.10), so real
    # matches (above the floor) pass while background text (within it) is excluded.
    _clear_env()
    assert round(_threshold(_real_self(), _status(0.60)), 3) == 0.50
    assert round(_threshold(_real_self(), _status(0.45)), 3) == 0.35


def test_missing_floor_falls_back_to_default():
    _clear_env()
    assert _threshold(_real_self(), _status(None)) == DEFAULT_RELEVANCE_THRESHOLD


def test_threshold_clamps_to_a_sane_band():
    # The old flat 0.38 cap is gone: a high calibrated floor now yields a
    # correspondingly high threshold (floor − 0.10), clamped to [0.15, 0.60].
    _clear_env()
    # High floor is honoured (no longer capped at 0.38) but the ceiling holds.
    assert round(_threshold(_real_self(), _status(0.55)), 3) == 0.45
    assert round(_threshold(_real_self(), _status(0.80)), 3) == 0.60  # clamped to max
    # Low floor clamps to the minimum, never below 0.15.
    assert round(_threshold(_real_self(), _status(0.20)), 3) == 0.15


def test_answer_mode_scales_the_threshold():
    # Deep dive is more permissive (lower floor); Only-from-sources is stricter
    # (higher floor); Balanced sits in between — all off the same base.
    _clear_env()
    base = _threshold(_real_self(), _status(None), "safe")
    deep = _threshold(_real_self(), _status(None), "deep")
    strict = _threshold(_real_self(), _status(None), "sources_only")
    assert deep < base < strict
    assert base == DEFAULT_RELEVANCE_THRESHOLD


def test_fake_embedding_ignores_calibrated_floor():
    _clear_env()
    assert _threshold(_fake_self(), _status(0.27)) == FAKE_EMBEDDING_RELEVANCE_THRESHOLD


def test_env_override_wins_over_everything():
    os.environ[RELEVANCE_THRESHOLD_ENV_VAR] = "0.5"
    try:
        assert _threshold(_real_self(), _status(0.27)) == 0.5
        assert _threshold(_fake_self(), _status(0.27)) == 0.5
    finally:
        _clear_env()
