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


def test_calibrated_floor_is_used_when_present():
    _clear_env()
    assert _threshold(_real_self(), _status(0.27)) == 0.27


def test_missing_floor_falls_back_to_default():
    _clear_env()
    assert _threshold(_real_self(), _status(None)) == DEFAULT_RELEVANCE_THRESHOLD


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
