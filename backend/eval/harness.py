"""Pure scoring for the golden-set run.

Given the labelled cases and the per-question outcomes (abstained? which sources?
best score?), compute the metrics that decide the embedder question (P5) and the
abstention floor: retrieval-hit@k, overblock rate, should-abstain accuracy, and
optionally hallucination rate. No I/O here — deterministic and unit-tested; the
runner (``eval/golden.py``) produces the outcomes and writes the reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
    QuestionCase,
)

PROJECT_CLASSES = (CLASS_PROJECT_PRECISE, CLASS_PROJECT_BROAD)


@dataclass(frozen=True)
class QuestionOutcome:
    """What retrieval did for one question."""

    question_id: str
    abstained: bool
    source_paths: tuple[str, ...]
    best_score: float
    # Generation-side, only when the run included answer generation: True when the
    # answer carried a hard grounding warning (cited no source / ungrounded term).
    hallucinated: bool | None = None


@dataclass(frozen=True)
class ClassMetrics:
    cls: str
    n: int
    retrieval_hit_at_k: float | None = None
    overblock_rate: float | None = None
    abstain_correct_rate: float | None = None
    hallucination_rate: float | None = None


@dataclass(frozen=True)
class EvalReport:
    embedder: str
    k: int
    total: int
    per_class: tuple[ClassMetrics, ...] = field(default_factory=tuple)
    overall_retrieval_hit_at_k: float | None = None
    overall_overblock_rate: float | None = None
    overall_should_abstain_accuracy: float | None = None
    overall_hallucination_rate: float | None = None


def case_is_hit(case: QuestionCase, outcome: QuestionOutcome) -> bool:
    """A retrieval hit: at least one expected path appears (as a substring) in a
    retrieved source path. Only meaningful for project_precise cases."""
    if not case.expected_paths:
        return False
    for expected in case.expected_paths:
        for path in outcome.source_paths:
            if expected in path:
                return True
    return False


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def compute_report(
    embedder: str,
    k: int,
    cases: list[QuestionCase],
    outcomes: list[QuestionOutcome],
) -> EvalReport:
    by_id = {o.question_id: o for o in outcomes}
    per_class: list[ClassMetrics] = []

    for cls in (CLASS_PROJECT_PRECISE, CLASS_PROJECT_BROAD, CLASS_SHOULD_ABSTAIN):
        cls_cases = [c for c in cases if c.cls == cls and c.id in by_id]
        if not cls_cases:
            continue
        outs = [by_id[c.id] for c in cls_cases]

        hit = (
            _mean([1.0 if case_is_hit(c, by_id[c.id]) else 0.0 for c in cls_cases])
            if cls == CLASS_PROJECT_PRECISE
            else None
        )
        # For project classes, abstaining is a miss (overblock).
        overblock = (
            _mean([1.0 if o.abstained else 0.0 for o in outs])
            if cls in PROJECT_CLASSES
            else None
        )
        # For the abstain class, abstaining is the correct behaviour.
        abstain_correct = (
            _mean([1.0 if o.abstained else 0.0 for o in outs])
            if cls == CLASS_SHOULD_ABSTAIN
            else None
        )
        halluc = _mean([1.0 if o.hallucinated else 0.0 for o in outs if o.hallucinated is not None])

        per_class.append(
            ClassMetrics(
                cls=cls,
                n=len(cls_cases),
                retrieval_hit_at_k=hit,
                overblock_rate=overblock,
                abstain_correct_rate=abstain_correct,
                hallucination_rate=halluc,
            )
        )

    precise = [c for c in cases if c.cls == CLASS_PROJECT_PRECISE and c.id in by_id]
    project = [c for c in cases if c.cls in PROJECT_CLASSES and c.id in by_id]
    abstain = [c for c in cases if c.cls == CLASS_SHOULD_ABSTAIN and c.id in by_id]
    project_hallu = [
        by_id[c.id].hallucinated for c in project if by_id[c.id].hallucinated is not None
    ]

    return EvalReport(
        embedder=embedder,
        k=k,
        total=len([c for c in cases if c.id in by_id]),
        per_class=tuple(per_class),
        overall_retrieval_hit_at_k=_mean(
            [1.0 if case_is_hit(c, by_id[c.id]) else 0.0 for c in precise]
        ),
        overall_overblock_rate=_mean([1.0 if by_id[c.id].abstained else 0.0 for c in project]),
        overall_should_abstain_accuracy=_mean(
            [1.0 if by_id[c.id].abstained else 0.0 for c in abstain]
        ),
        overall_hallucination_rate=_mean([1.0 if h else 0.0 for h in project_hallu]),
    )


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def render_markdown(
    report: EvalReport,
    cases: list[QuestionCase],
    outcomes: list[QuestionOutcome],
) -> str:
    by_id = {o.question_id: o for o in outcomes}
    lines: list[str] = []
    lines.append(f"# Golden-set eval — `{report.embedder}`")
    lines.append("")
    lines.append(f"- Questions scored: **{report.total}** · top-k = {report.k}")
    lines.append(f"- Retrieval hit@{report.k} (precise): **{_pct(report.overall_retrieval_hit_at_k)}**")
    lines.append(f"- Overblock rate (project qs wrongly abstained): **{_pct(report.overall_overblock_rate)}**")
    lines.append(f"- Should-abstain accuracy: **{_pct(report.overall_should_abstain_accuracy)}**")
    if report.overall_hallucination_rate is not None:
        lines.append(f"- Hallucination rate (generation): **{_pct(report.overall_hallucination_rate)}**")
    lines.append("")
    lines.append("## By class")
    lines.append("")
    lines.append("| Class | N | hit@k | overblock | abstain-correct | halluc |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for cm in report.per_class:
        lines.append(
            f"| {cm.cls} | {cm.n} | {_pct(cm.retrieval_hit_at_k)} | "
            f"{_pct(cm.overblock_rate)} | {_pct(cm.abstain_correct_rate)} | "
            f"{_pct(cm.hallucination_rate)} |"
        )
    lines.append("")
    lines.append("## Failures to eyeball")
    lines.append("")
    any_fail = False
    for c in cases:
        o = by_id.get(c.id)
        if o is None:
            continue
        bad = (
            (c.cls == CLASS_PROJECT_PRECISE and not case_is_hit(c, o))
            or (c.cls in PROJECT_CLASSES and o.abstained)
            or (c.cls == CLASS_SHOULD_ABSTAIN and not o.abstained)
        )
        if not bad:
            continue
        any_fail = True
        note = "abstained" if o.abstained else f"sources={list(o.source_paths)[:3]}"
        lines.append(f"- `{c.id}` ({c.cls}, score={o.best_score:.3f}): {note} — {c.question}")
    if not any_fail:
        lines.append("_None — clean run._")
    lines.append("")
    return "\n".join(lines)


def report_to_dict(
    report: EvalReport,
    cases: list[QuestionCase],
    outcomes: list[QuestionOutcome],
) -> dict:
    by_case = {c.id: c for c in cases}
    return {
        "embedder": report.embedder,
        "k": report.k,
        "total": report.total,
        "overall": {
            "retrieval_hit_at_k": report.overall_retrieval_hit_at_k,
            "overblock_rate": report.overall_overblock_rate,
            "should_abstain_accuracy": report.overall_should_abstain_accuracy,
            "hallucination_rate": report.overall_hallucination_rate,
        },
        "per_class": [
            {
                "cls": cm.cls,
                "n": cm.n,
                "retrieval_hit_at_k": cm.retrieval_hit_at_k,
                "overblock_rate": cm.overblock_rate,
                "abstain_correct_rate": cm.abstain_correct_rate,
                "hallucination_rate": cm.hallucination_rate,
            }
            for cm in report.per_class
        ],
        "questions": [
            {
                "id": o.question_id,
                "cls": by_case[o.question_id].cls if o.question_id in by_case else "?",
                "abstained": o.abstained,
                "best_score": round(o.best_score, 4),
                "source_paths": list(o.source_paths),
                "hallucinated": o.hallucinated,
                "hit": (
                    case_is_hit(by_case[o.question_id], o)
                    if o.question_id in by_case
                    and by_case[o.question_id].cls == CLASS_PROJECT_PRECISE
                    else None
                ),
            }
            for o in outcomes
        ],
    }
