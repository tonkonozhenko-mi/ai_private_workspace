from app.core.domain.context_budget import (
    chunk_char_budget,
    estimate_tokens,
    fit_context_results,
)
from app.core.domain.indexing import ContextSearchResult


def _result(chunk_id: str, content: str) -> ContextSearchResult:
    return ContextSearchResult(
        chunk_id=chunk_id,
        source_path=f"{chunk_id}.py",
        content=content,
        score=1.0,
        metadata={},
    )


def test_estimate_tokens_chars_over_four():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 40) == 10


def test_budget_shrinks_as_window_fills():
    big_window = chunk_char_budget(8192)
    small_window = chunk_char_budget(2048)
    assert big_window > small_window
    # Memory + history eat into the chunk budget.
    with_memory = chunk_char_budget(8192, memory_text="x" * 4000)
    assert with_memory < big_window
    with_history = chunk_char_budget(8192, history=[("user", "y" * 4000)])
    assert with_history < big_window


def test_budget_never_negative_or_below_floor():
    # Tiny window fully consumed by reserves still yields the minimum floor.
    assert chunk_char_budget(64) >= 600


def test_fit_keeps_whole_chunks_until_budget():
    results = [_result(str(i), "a" * 400) for i in range(10)]
    fitted = fit_context_results(results, char_budget=1000)
    # 400+80 per chunk -> 2 fit in 1000, the 3rd would overflow.
    assert len(fitted) == 2
    assert [r.chunk_id for r in fitted] == ["0", "1"]


def test_fit_truncates_a_lone_oversized_first_chunk():
    results = [_result("big", "z" * 5000)]
    fitted = fit_context_results(results, char_budget=500)
    assert len(fitted) == 1
    assert len(fitted[0].content) <= 500
    assert fitted[0].content == "z" * len(fitted[0].content)


def test_fit_returns_all_when_budget_is_ample():
    results = [_result(str(i), "a" * 100) for i in range(3)]
    fitted = fit_context_results(results, char_budget=100_000)
    assert len(fitted) == 3
