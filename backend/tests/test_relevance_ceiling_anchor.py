"""The chit-chat ceiling is an anchor, not a discount.

Pinned on the numbers from the first external eval run (online-boutique,
2026-07-13): the noise floor clamped at 0.6, so the bar sat at 0.5 — below the
0.559 that neutral, off-topic questions actually reached against that corpus.
"What is Google's stock price today?" (0.590) was duly answered from the
project's source files. A bar below the ceiling admits small talk by
construction; these tests make sure it cannot happen again.
"""

from app.core.domain.index_status import WorkspaceIndexStatus
from app.core.use_cases.ask_workspace_question import (
    RELEVANCE_FLOOR_MARGIN,
    RELEVANCE_PROBE_MARGIN,
    AskWorkspaceQuestionUseCase,
)


class _RealEmbedder:
    provider_name = "ollama"


def _use_case() -> AskWorkspaceQuestionUseCase:
    use_case = AskWorkspaceQuestionUseCase(
        workspace_repository=None,
        embedding_provider=_RealEmbedder(),
        vector_store=None,
        llm_provider_factory=None,
        index_status_repository=None,
    )
    return use_case


def _status(floor: float | None, ceiling: float | None) -> WorkspaceIndexStatus:
    return WorkspaceIndexStatus(
        workspace_id="ws",
        status="indexed",
        chunks_count=100,
        indexed_files_count=10,
        skipped_files_count=0,
        last_indexed_at=None,
        last_error=None,
        relevance_floor=floor,
        relevance_probe_ceiling=ceiling,
    )


def test_the_bar_clears_the_ceiling_even_when_the_floor_says_otherwise():
    # online-boutique: floor 0.6 (clamped) → the old min() gave 0.5, under the
    # 0.559 that chit-chat reached.
    threshold = _use_case()._relevance_threshold(_status(floor=0.6, ceiling=0.559))
    assert abs(threshold - (0.559 + RELEVANCE_PROBE_MARGIN)) < 1e-9
    assert threshold > 0.559


def test_a_low_ceiling_still_lowers_the_bar():
    # tf-aws-vpc: ceiling 0.458 → 0.488, exactly what it was before. The fix
    # changes nothing where the two anchors already agreed.
    threshold = _use_case()._relevance_threshold(_status(floor=0.588, ceiling=0.458))
    assert abs(threshold - 0.488) < 1e-9


def test_without_a_ceiling_the_floor_still_carries_the_index():
    # An index built before probes existed, or too small to sample one.
    floor = 0.55
    threshold = _use_case()._relevance_threshold(_status(floor=floor, ceiling=None))
    assert abs(threshold - (floor - RELEVANCE_FLOOR_MARGIN)) < 1e-9


def test_the_bar_is_never_below_the_ceiling_whatever_the_floor_says():
    """The invariant, across floors that agree with the ceiling and floors that
    contradict it."""
    use_case = _use_case()
    for ceiling in (0.2, 0.35, 0.458, 0.559, 0.7):
        for floor in (0.1, 0.3, 0.5, 0.6, 0.9):
            threshold = use_case._relevance_threshold(_status(floor=floor, ceiling=ceiling))
            # Clamped at RELEVANCE_FLOOR_MAX (0.6), so a ceiling above it cannot be
            # cleared — but within the clamp, the bar always sits above the ceiling.
            if ceiling + RELEVANCE_PROBE_MARGIN <= 0.6:
                assert threshold >= ceiling, (floor, ceiling, threshold)
