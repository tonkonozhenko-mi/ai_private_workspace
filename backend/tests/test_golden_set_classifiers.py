"""Deterministic guard rails for the golden set, runnable in CI without an
embedder or an LLM.

The retrieval eval needs Ollama and minutes to run, so classifier regressions
(the chit-chat router, the abstention-threshold formula) only surfaced on a manual
run. These are pure functions, so we can pin their behaviour against the labelled
golden set in seconds: every should-abstain question must route to general chat,
no project question may, and the threshold must track the calibrated floor.
"""

from types import SimpleNamespace

from app.core.domain.question_intent import looks_general_chat
from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
    golden_set,
)

_PROJECT_CLASSES = (CLASS_PROJECT_PRECISE, CLASS_PROJECT_BROAD)


def test_every_should_abstain_question_routes_to_general_chat():
    misses = [
        c.id
        for c in golden_set()
        if c.cls == CLASS_SHOULD_ABSTAIN and not looks_general_chat(c.question)
    ]
    assert not misses, f"should-abstain questions NOT routed to general chat: {misses}"


def test_no_project_question_is_routed_to_general_chat():
    wrong = [
        c.id
        for c in golden_set()
        if c.cls in _PROJECT_CLASSES and looks_general_chat(c.question)
    ]
    assert not wrong, f"project questions wrongly routed to general chat: {wrong}"


def _threshold_for_floor(floor: float | None) -> float:
    """Build a minimal use case (no I/O touched by ``_relevance_threshold``) and ask
    it for the abstention threshold at a given calibrated floor."""
    from app.core.domain.index_status import WorkspaceIndexStatus
    from app.core.use_cases.ask_workspace_question import AskWorkspaceQuestionUseCase

    uc = AskWorkspaceQuestionUseCase(
        workspace_repository=SimpleNamespace(get=lambda _wid: None),
        embedding_provider=SimpleNamespace(provider_name="ollama"),
        vector_store=SimpleNamespace(),
        llm_provider_factory=None,
        index_status_repository=SimpleNamespace(get=lambda _wid: None),
    )
    status = (
        None
        if floor is None
        else WorkspaceIndexStatus(
            workspace_id="w",
            status="indexed",
            indexed_files_count=0,
            chunks_count=1,
            skipped_files_count=0,
            last_indexed_at=None,
            last_error=None,
            embedding_model="nomic-embed-text",
            relevance_floor=floor,
        )
    )
    return uc._relevance_threshold(status, None)


def test_threshold_sits_a_margin_below_a_normal_floor():
    from app.core.use_cases.ask_workspace_question import (
        RELEVANCE_FLOOR_MARGIN,
    )

    # A mid-range calibrated floor → threshold is exactly floor − margin.
    assert _threshold_for_floor(0.60) == round(0.60 - RELEVANCE_FLOOR_MARGIN, 10)


def test_threshold_is_clamped_to_the_floor_band():
    from app.core.use_cases.ask_workspace_question import (
        RELEVANCE_FLOOR_MAX,
        RELEVANCE_FLOOR_MIN,
    )

    # A tiny floor can't push the threshold below the band's minimum…
    assert _threshold_for_floor(0.05) == RELEVANCE_FLOOR_MIN
    # …and a huge floor can't push it above the maximum.
    assert _threshold_for_floor(5.0) == RELEVANCE_FLOOR_MAX


def test_threshold_falls_back_to_default_without_a_calibrated_floor():
    from app.core.use_cases.ask_workspace_question import DEFAULT_RELEVANCE_THRESHOLD

    assert _threshold_for_floor(None) == DEFAULT_RELEVANCE_THRESHOLD


if __name__ == "__main__":
    # Router checks run without heavy deps; threshold checks need the app package.
    test_every_should_abstain_question_routes_to_general_chat()
    print("PASS test_every_should_abstain_question_routes_to_general_chat")
    test_no_project_question_is_routed_to_general_chat()
    print("PASS test_no_project_question_is_routed_to_general_chat")
