"""P7a: query rewrite defaults to the reranker state. P7b: synonym expansion is
applied to the retrieval query before it reaches the vector store."""

import os

from app.core.use_cases.ask_workspace_question import (
    QUERY_REWRITE_ENV_VAR,
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionUseCase,
)


def _uc(**over):
    uc = AskWorkspaceQuestionUseCase(
        workspace_repository=None,
        embedding_provider=None,
        vector_store=None,
        llm_provider_factory=None,
        index_status_repository=None,
        **over,
    )
    return uc


class _Reranker:
    def __init__(self, enabled):
        self.enabled = enabled


# --- P7a: rewrite defaults to reranker state -----------------------------


def test_rewrite_off_without_reranker():
    os.environ.pop(QUERY_REWRITE_ENV_VAR, None)
    assert _uc(reranker=None).enable_query_rewrite is False
    assert _uc(reranker=_Reranker(False)).enable_query_rewrite is False


def test_rewrite_on_with_active_reranker():
    os.environ.pop(QUERY_REWRITE_ENV_VAR, None)
    assert _uc(reranker=_Reranker(True)).enable_query_rewrite is True


def test_env_override_wins_both_ways():
    try:
        os.environ[QUERY_REWRITE_ENV_VAR] = "off"
        assert _uc(reranker=_Reranker(True)).enable_query_rewrite is False
        os.environ[QUERY_REWRITE_ENV_VAR] = "on"
        assert _uc(reranker=None).enable_query_rewrite is True
    finally:
        os.environ.pop(QUERY_REWRITE_ENV_VAR, None)


def test_explicit_flag_beats_everything():
    assert _uc(reranker=_Reranker(True), enable_query_rewrite=False).enable_query_rewrite is False
    assert _uc(reranker=None, enable_query_rewrite=True).enable_query_rewrite is True


# --- P7b: synonym expansion reaches the vector store ---------------------


class _CapturingStore:
    def __init__(self):
        self.query_text = None

    def search(self, *, query_text=None, **kwargs):
        self.query_text = query_text
        return []


class _Embed:
    provider_name = "test"
    model_name = "test-embed"
    embedding_dimension = 3

    def embed_text(self, text):
        return [0.1, 0.2, 0.3]


def test_synonyms_are_expanded_in_the_retrieval_query():
    os.environ.pop(QUERY_REWRITE_ENV_VAR, None)
    store = _CapturingStore()
    uc = _uc()
    uc.embedding_provider = _Embed()
    uc.vector_store = store
    uc._conversation_history = lambda request: []
    request = AskWorkspaceQuestionInput(
        workspace_id="w",
        question="What Content-Security-Policy does the desktop app set?",
    )
    uc._search_context(request, llm_provider=None)
    assert store.query_text is not None
    # the file uses "csp"; expansion must have added it to the query
    assert "csp" in store.query_text.lower()
    # original wording is preserved
    assert "content-security-policy" in store.query_text.lower()
