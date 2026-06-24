"""The project-understanding prompt fits the model's context window: the retrieved
context is budgeted by the window so a large project includes fewer/shorter
sources instead of overflowing (which made llama.cpp return HTTP 400)."""

from app.core.domain.indexing import ContextSearchResult
from app.core.use_cases.generate_project_understanding import (
    MAX_TOTAL_CHARS,
    GenerateProjectUnderstandingUseCase,
)


class _Embedder:
    provider_name = "llamacpp"
    model_name = "qwen3-embedding-0.6b"

    def embed_text(self, _text):
        return [0.0, 0.1, 0.2]


class _VectorStore:
    def __init__(self, results):
        self._results = results

    def search(self, **_kwargs):
        return list(self._results)


def _use_case(max_context_tokens, results=()):
    return GenerateProjectUnderstandingUseCase(
        workspace_repository=None,
        embedding_provider=_Embedder(),
        vector_store=_VectorStore(results),
        llm_provider_factory=None,
        index_status_repository=None,
        selection_repository=None,
        understanding_repository=None,
        max_context_tokens=max_context_tokens,
    )


def test_budget_shrinks_for_a_small_window():
    # 4096 window → (4096 - 1024 - 1536) tokens * 4 chars = 6144, under the cap.
    assert _use_case(4096)._content_char_budget() == 6144


def test_budget_capped_for_a_large_window():
    # A big window does not bloat the prompt beyond the static cap.
    assert _use_case(32768)._content_char_budget() == MAX_TOTAL_CHARS


def test_tiny_window_keeps_a_minimum():
    assert _use_case(1024)._content_char_budget() == 2000


def test_retrieval_truncates_to_fit_the_window():
    big = ContextSearchResult(
        chunk_id="c1",
        source_path="a.py",
        content="x" * 50000,
        score=0.9,
        metadata={},
    )
    results = _use_case(4096, results=[big])._retrieve_context("w")
    assert len(results) == 1
    assert len(results[0].content) <= 6144  # truncated to the budget
