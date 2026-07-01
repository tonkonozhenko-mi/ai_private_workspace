"""Deterministic, offline evaluation of project-memory selection.

A sibling of ``answer_eval`` (which scores retrieval): this scores the *memory*
layer. For a given question over a fixed set of memory items, we know which notes
*should* be recalled and which must *not* be (a superseded/obsolete note, or a
stale one that should be down-ranked out). Selection is pure keyword + pin +
recency + confidence/freshness/stale weighting, so scoring it is fully
deterministic — a stable regression guard for memory ranking changes, with no
LLM and no flakiness.

The metrics mirror the ones worth tracking for "does memory help or hurt":
relevant-recall (did the right notes surface), stale-usage (did a flagged note
sneak in), and leak-rate (did a forbidden/obsolete note surface).

Everything here is pure and trivially testable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.domain.project_memory import (
    MemoryItem,
    MemoryStatus,
    select_relevant_memory,
)

# A selector takes (items, query, limit) and returns the recalled items. The
# default is the deterministic keyword selector; tests can pass a semantic-aware
# one (e.g. the compose use case's parallel retrieval) to score paraphrase recall.
MemorySelector = Callable[[list[MemoryItem], str, int], list[MemoryItem]]


def _default_selector(items: list[MemoryItem], query: str, limit: int) -> list[MemoryItem]:
    return select_relevant_memory(items, query, limit=limit)


@dataclass(frozen=True)
class MemoryEvalCase:
    question: str
    items: list[MemoryItem]
    # Ids that SHOULD be recalled for this question.
    expect_relevant_ids: list[str] = field(default_factory=list)
    # Ids that must NOT be recalled — e.g. an obsolete/superseded note, or a
    # known-irrelevant one. Recalling any of these is a leak.
    forbid_ids: list[str] = field(default_factory=list)
    limit: int = 6


@dataclass(frozen=True)
class MemoryCaseScore:
    question: str
    recalled_ids: list[str]
    relevant_hits: int  # how many expect_relevant_ids were recalled
    relevant_total: int
    relevant_recall: float  # hits / total (1.0 when nothing expected)
    used_stale: bool  # a recalled note is flagged stale
    used_obsolete: bool  # a recalled note is obsolete (should never happen)
    leaked_ids: list[str]  # forbidden ids that were recalled
    passed: bool  # all expected recalled, nothing forbidden/obsolete leaked


@dataclass(frozen=True)
class MemoryEvalReport:
    total: int
    passed: int
    relevant_recall: float  # average across cases that expected something
    stale_usage_rate: float  # fraction of cases that recalled a stale note
    leak_rate: float  # fraction of cases where a forbidden/obsolete note leaked
    scores: list[MemoryCaseScore] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def helpfulness_rate(self) -> float:
        """Of the cases where memory *should* have helped (they declared expected
        notes), the fraction where it actually surfaced all of them. Answers
        "does memory help?" — 1.0 means every case that needed a note got it."""
        expecting = [s for s in self.scores if s.relevant_total > 0]
        if not expecting:
            return 1.0
        helped = sum(1 for s in expecting if s.relevant_recall >= 1.0)
        return helped / len(expecting)


def score_memory_case(
    case: MemoryEvalCase, select_fn: MemorySelector | None = None
) -> MemoryCaseScore:
    """Run the memory selector for one case and score what it recalled.

    ``select_fn`` defaults to the deterministic keyword selector; pass a
    semantic-aware one to score paraphrase recall (catches a note that means the
    same thing in different words)."""
    selector = select_fn or _default_selector
    recalled = selector(case.items, case.question, case.limit)
    recalled_ids = [i.id for i in recalled]
    recalled_set = set(recalled_ids)

    expected = set(case.expect_relevant_ids)
    hits = len(expected & recalled_set)
    relevant_total = len(expected)
    relevant_recall = (hits / relevant_total) if relevant_total else 1.0

    used_stale = any(i.stale for i in recalled)
    used_obsolete = any(i.status == MemoryStatus.OBSOLETE for i in recalled)
    leaked = [fid for fid in case.forbid_ids if fid in recalled_set]

    passed = relevant_recall >= 1.0 and not leaked and not used_obsolete
    return MemoryCaseScore(
        question=case.question,
        recalled_ids=recalled_ids,
        relevant_hits=hits,
        relevant_total=relevant_total,
        relevant_recall=relevant_recall,
        used_stale=used_stale,
        used_obsolete=used_obsolete,
        leaked_ids=leaked,
        passed=passed,
    )


def aggregate_memory(scores: list[MemoryCaseScore]) -> MemoryEvalReport:
    if not scores:
        return MemoryEvalReport(
            total=0, passed=0, relevant_recall=0.0, stale_usage_rate=0.0, leak_rate=0.0
        )
    passed = sum(1 for s in scores if s.passed)
    recalls = [s.relevant_recall for s in scores if s.relevant_total > 0]
    relevant_recall = sum(recalls) / len(recalls) if recalls else 1.0
    stale_usage_rate = sum(1 for s in scores if s.used_stale) / len(scores)
    leak_rate = sum(1 for s in scores if s.leaked_ids or s.used_obsolete) / len(scores)
    return MemoryEvalReport(
        total=len(scores),
        passed=passed,
        relevant_recall=relevant_recall,
        stale_usage_rate=stale_usage_rate,
        leak_rate=leak_rate,
        scores=list(scores),
    )


def run_memory_eval(
    cases: list[MemoryEvalCase], select_fn: MemorySelector | None = None
) -> MemoryEvalReport:
    """Score a whole golden set of memory cases in one call."""
    return aggregate_memory([score_memory_case(c, select_fn) for c in cases])
