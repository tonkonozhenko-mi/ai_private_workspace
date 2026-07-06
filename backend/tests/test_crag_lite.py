"""CRAG-lite: one bounded corrective retrieval + optional regeneration."""

from app.core.domain.indexing import ContextSearchResult
from app.core.domain.rag import RagQualityWarning
from app.core.use_cases.ask_workspace_question import (
    AskWorkspaceQuestionInput,
    AskWorkspaceQuestionUseCase,
)


class _LLM:
    def __init__(self, reply="search terms magic"):
        self.reply = reply
        self.calls = 0

    def generate(self, prompt, images, temperature, think, history):
        self.calls += 1
        return self.reply


def _uc(**over) -> AskWorkspaceQuestionUseCase:
    uc = AskWorkspaceQuestionUseCase(
        workspace_repository=None,
        embedding_provider=None,
        vector_store=None,
        llm_provider_factory=None,
        index_status_repository=None,
    )
    for k, v in over.items():
        setattr(uc, k, v)
    return uc


def _result(path, score, content="body"):
    return ContextSearchResult(
        chunk_id=f"ws:{path}:0", source_path=path, content=content, score=score, metadata={}
    )


def _req(question="how does the deployment pipeline work?"):
    return AskWorkspaceQuestionInput(workspace_id="ws", question=question)


def _hard_warning():
    return RagQualityWarning(
        code="answer_missing_source_paths", message="m", severity="medium", evidence=[]
    )


# --- forced rewrite ------------------------------------------------------


def test_rewrite_query_runs_when_forced_even_if_disabled():
    uc = _uc(enable_query_rewrite=False)
    uc._conversation_history = lambda request: []
    llm = _LLM(reply="deployment ci cd pipeline")
    out = uc._rewrite_query("base", _req(), llm, force=True)
    assert llm.calls == 1
    assert "base" in out  # merged with original


def test_rewrite_query_skipped_when_disabled_and_not_forced():
    uc = _uc(enable_query_rewrite=False)
    llm = _LLM()
    assert uc._rewrite_query("base", _req(), llm, force=False) == "base"
    assert llm.calls == 0


# --- corrective retrieval gate ------------------------------------------


def test_corrective_retrieval_none_for_chit_chat():
    uc = _uc()
    uc._search_context = lambda *a, **k: [_result("a.py", 0.9)]
    assert uc._corrective_retrieval(_req("hello there, how are you?"), _LLM()) is None


def test_corrective_retrieval_returns_results_for_project_question():
    uc = _uc()
    seen = {}
    uc._search_context = lambda request, provider, force_rewrite=False: (
        seen.update(force=force_rewrite) or [_result("a.py", 0.7)]
    )
    out = uc._corrective_retrieval(_req(), _LLM())
    assert out and out[0].source_path == "a.py"
    assert seen["force"] is True  # forced rewrite path used


def test_corrective_retrieval_fail_open_returns_none():
    uc = _uc()

    def boom(*a, **k):
        raise RuntimeError("vector down")

    uc._search_context = boom
    assert uc._corrective_retrieval(_req(), _LLM()) is None


# --- corrective regeneration (trigger b) --------------------------------


def test_regeneration_skipped_without_hard_warnings():
    uc = _uc()
    soft = [
        RagQualityWarning(code="quote_not_in_sources", message="m", severity="review", evidence=[])
    ]
    assert uc._corrective_regeneration(_req(), _LLM(), [], soft, 0.6) is None


def test_regeneration_skipped_when_no_score_improvement():
    uc = _uc()
    uc._corrective_retrieval = lambda request, provider: [_result("a.py", 0.5)]
    # corrected best (0.5) <= current best (0.6) → no regeneration
    assert uc._corrective_regeneration(_req(), _LLM(), [], [_hard_warning()], 0.6) is None


def test_regeneration_adopted_when_grounding_improves():
    uc = _uc()
    uc._corrective_retrieval = lambda request, provider: [
        _result("main.tf", 0.9, "terraform backend s3")
    ]
    uc._grounded_prompt = lambda request, provider, ctx, hist: (ctx, "PROMPT", 0, 0, {})
    uc._generate_answer_with_usage = lambda *a, **k: ("Backend is S3 (main.tf).", None)
    out = uc._corrective_regeneration(_req(), _LLM(), [], [_hard_warning()], 0.4)
    assert out is not None
    assert out["answer"] == "Backend is S3 (main.tf)."
    assert out["sources"][0].source_path == "main.tf"
    # the regenerated answer mentions main.tf → no answer_missing_source_paths
    assert not any(w.code == "answer_missing_source_paths" for w in out["warnings"])


def test_regeneration_rejected_when_still_ungrounded():
    uc = _uc()
    uc._corrective_retrieval = lambda request, provider: [
        _result("main.tf", 0.9, "terraform backend s3")
    ]
    uc._grounded_prompt = lambda request, provider, ctx, hist: (ctx, "PROMPT", 0, 0, {})
    # regenerated answer still cites no source path → not better → keep original
    uc._generate_answer_with_usage = lambda *a, **k: ("It is configured somewhere.", None)
    assert uc._corrective_regeneration(_req(), _LLM(), [], [_hard_warning()], 0.4) is None
