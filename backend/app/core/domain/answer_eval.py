"""Deterministic, offline evaluation of retrieval quality.

A small "golden questions" harness: for each question we know which file(s) the
answer should be grounded in (and optionally which keywords the answer should
contain). Scoring the *retrieval* (did the right files come back?) is fully
deterministic given a fixed index + embedder, so it makes a stable regression
guard for RAG changes — no LLM, no flakiness. Answer-keyword scoring is offered
too for when a caller has a generated answer to check.

Everything here is pure and trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Mirrors Ask's DEFAULT_RELEVANCE_THRESHOLD: below this top similarity, the
# system should treat retrieval as "nothing confident found" and abstain rather
# than answer from weak context (the main hallucination vector on small models).
# Kept as a local constant so this pure domain doesn't import the LLM use case.
DEFAULT_ABSTAIN_THRESHOLD = 0.38


@dataclass(frozen=True)
class EvalCase:
    question: str
    # Source paths the answer should be grounded in (retrieval must surface them).
    expect_sources: list[str] = field(default_factory=list)
    # Optional substrings the generated answer should contain (case-insensitive).
    expect_keywords: list[str] = field(default_factory=list)
    # A "negative" / out-of-scope case: the project has no answer, so the system
    # should ABSTAIN (retrieval finds nothing confident) instead of inventing one.
    expect_abstain: bool = False


@dataclass(frozen=True)
class CaseScore:
    question: str
    retrieved_sources: list[str]
    matched_sources: list[str]
    source_recall: float  # fraction of expect_sources that were retrieved
    keyword_hits: int
    keyword_total: int
    passed: bool
    expect_abstain: bool = False
    top_score: float = 1.0
    # For an abstain case: did the system correctly abstain (find nothing confident)?
    abstained: bool | None = None
    # For a positive case: did the safeguards wrongly abstain despite the answer
    # being available (top_score below the threshold)? True = a safety over-block.
    overblocked: bool = False


@dataclass(frozen=True)
class EvalReport:
    total: int
    passed: int
    source_recall: float  # average across cases that declared expect_sources
    keyword_recall: float  # average across cases that declared expect_keywords
    abstain_total: int = 0  # number of negative (out-of-scope) cases
    abstain_correct: int = 0  # negatives the system correctly abstained on
    scores: list[CaseScore] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def hallucination_rate(self) -> float:
        """Of the out-of-scope questions, the fraction where retrieval handed back
        confident context anyway — i.e. where the model would likely fabricate a
        project-specific answer. Lower is better; 0.0 means it abstained on all."""
        if self.abstain_total == 0:
            return 0.0
        return (self.abstain_total - self.abstain_correct) / self.abstain_total

    @property
    def overblock_rate(self) -> float:
        """Of the positive (should-answer) cases, the fraction the safeguards would
        wrongly refuse (top similarity below the abstain threshold). Lower is
        better; the mirror of hallucination_rate — measures over-caution."""
        positives = [s for s in self.scores if not s.expect_abstain]
        if not positives:
            return 0.0
        return sum(1 for s in positives if s.overblocked) / len(positives)


def _norm(path: str) -> str:
    return path.strip().strip("/").lower()


def score_case(
    case: EvalCase,
    retrieved_sources: list[str],
    answer_text: str = "",
    *,
    top_score: float = 1.0,
    abstain_threshold: float = DEFAULT_ABSTAIN_THRESHOLD,
) -> CaseScore:
    """Score one case against the retrieved source paths (and an optional answer).

    Positive case: a source is matched if an expected path equals a retrieved path
    or is a suffix of one ("main.tf" matches "app/main.tf"); it passes when every
    expected source was retrieved and every expected keyword is in the answer.

    Negative case (``expect_abstain``): it passes when retrieval found nothing
    confident (``top_score`` below ``abstain_threshold``), so the system would
    honestly say "not found in the project" instead of inventing an answer.
    """
    retrieved_norm = [_norm(p) for p in retrieved_sources]
    matched: list[str] = []
    for expected in case.expect_sources:
        target = _norm(expected)
        if any(target == r or r.endswith("/" + target) or r == target for r in retrieved_norm):
            matched.append(expected)
    source_recall = (len(matched) / len(case.expect_sources)) if case.expect_sources else 1.0

    answer_lower = (answer_text or "").lower()
    keyword_hits = sum(1 for kw in case.expect_keywords if kw.lower() in answer_lower)
    keyword_total = len(case.expect_keywords)
    keyword_ok = keyword_hits == keyword_total

    if case.expect_abstain:
        abstained = top_score < abstain_threshold
        return CaseScore(
            question=case.question,
            retrieved_sources=list(retrieved_sources),
            matched_sources=matched,
            source_recall=source_recall,
            keyword_hits=keyword_hits,
            keyword_total=keyword_total,
            passed=abstained,
            expect_abstain=True,
            top_score=top_score,
            abstained=abstained,
        )

    passed = source_recall >= 1.0 and keyword_ok
    # A positive case whose top similarity fell below the abstain threshold would
    # be silently refused by the safeguards even though the answer was there.
    overblocked = top_score < abstain_threshold
    return CaseScore(
        question=case.question,
        retrieved_sources=list(retrieved_sources),
        matched_sources=matched,
        source_recall=source_recall,
        keyword_hits=keyword_hits,
        keyword_total=keyword_total,
        passed=passed,
        expect_abstain=False,
        top_score=top_score,
        overblocked=overblocked,
    )


def aggregate(scores: list[CaseScore]) -> EvalReport:
    if not scores:
        return EvalReport(total=0, passed=0, source_recall=0.0, keyword_recall=0.0, scores=[])
    passed = sum(1 for s in scores if s.passed)
    # Source recall is only meaningful for positive (non-abstain) cases.
    src = [s.source_recall for s in scores if not s.expect_abstain]
    source_recall = sum(src) / len(src) if src else 1.0
    kw_scores = [(s.keyword_hits / s.keyword_total) for s in scores if s.keyword_total > 0]
    keyword_recall = sum(kw_scores) / len(kw_scores) if kw_scores else 1.0
    abstain = [s for s in scores if s.expect_abstain]
    return EvalReport(
        total=len(scores),
        passed=passed,
        source_recall=source_recall,
        keyword_recall=keyword_recall,
        abstain_total=len(abstain),
        abstain_correct=sum(1 for s in abstain if s.abstained),
        scores=list(scores),
    )
