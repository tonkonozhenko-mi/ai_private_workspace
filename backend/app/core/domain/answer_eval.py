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


@dataclass(frozen=True)
class EvalCase:
    question: str
    # Source paths the answer should be grounded in (retrieval must surface them).
    expect_sources: list[str] = field(default_factory=list)
    # Optional substrings the generated answer should contain (case-insensitive).
    expect_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CaseScore:
    question: str
    retrieved_sources: list[str]
    matched_sources: list[str]
    source_recall: float  # fraction of expect_sources that were retrieved
    keyword_hits: int
    keyword_total: int
    passed: bool


@dataclass(frozen=True)
class EvalReport:
    total: int
    passed: int
    source_recall: float  # average across cases that declared expect_sources
    keyword_recall: float  # average across cases that declared expect_keywords
    scores: list[CaseScore] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def _norm(path: str) -> str:
    return path.strip().strip("/").lower()


def score_case(case: EvalCase, retrieved_sources: list[str], answer_text: str = "") -> CaseScore:
    """Score one case against the retrieved source paths (and an optional answer).

    A source is matched if an expected path equals a retrieved path or is a
    suffix of one (so "main.tf" matches "app/main.tf"). A case passes when every
    expected source was retrieved and every expected keyword is in the answer.
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

    passed = source_recall >= 1.0 and keyword_ok
    return CaseScore(
        question=case.question,
        retrieved_sources=list(retrieved_sources),
        matched_sources=matched,
        source_recall=source_recall,
        keyword_hits=keyword_hits,
        keyword_total=keyword_total,
        passed=passed,
    )


def aggregate(scores: list[CaseScore]) -> EvalReport:
    if not scores:
        return EvalReport(total=0, passed=0, source_recall=0.0, keyword_recall=0.0, scores=[])
    passed = sum(1 for s in scores if s.passed)
    src = [s.source_recall for s in scores]
    source_recall = sum(src) / len(src)
    kw_scores = [
        (s.keyword_hits / s.keyword_total) for s in scores if s.keyword_total > 0
    ]
    keyword_recall = sum(kw_scores) / len(kw_scores) if kw_scores else 1.0
    return EvalReport(
        total=len(scores),
        passed=passed,
        source_recall=source_recall,
        keyword_recall=keyword_recall,
        scores=list(scores),
    )
