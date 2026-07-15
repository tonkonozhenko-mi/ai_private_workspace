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
    # Generation-side, only when the run included answer generation. ``hallucinated``
    # is the PRODUCT number: whether the answer STILL carried a hard grounding warning
    # after the app's corrective regeneration pass (CRAG trigger b) ran. ``raw_``
    # is the same measurement on the first, uncorrected answer — the model on its own.
    # The pair (raw → product) shows the corrective sieve is a working mechanism, not
    # decoration. ``warning_codes`` are the product answer's warning codes and
    # ``answer`` its text — populated only when the run saved answers, for eyeballing.
    hallucinated: bool | None = None
    raw_hallucinated: bool | None = None
    warning_codes: tuple[str, ...] = ()
    answer: str | None = None
    # Wall-clock seconds spent generating this answer (the model call and the app's
    # corrective pass around it — nothing else). Published because one question on
    # the Terraform corpus took long enough to look like a bug, and "it is slow" is
    # not an answer: the number is, and it is the same number on both engines.
    generation_seconds: float | None = None
    # For should-abstain questions that cleared the retrieval threshold and were
    # answered anyway: True when the answer is an explicit, clean "the files do
    # not contain this". The adversarial cases forced the distinction — a
    # project-flavoured question about a technology the corpus never mentions can
    # legitimately score above the threshold (its entities are real), and the
    # honest negative it then gets is not a failure of the class, it is the class
    # passed by other means: no fabrication happened, and the person learned more
    # than a refusal would have told them.
    honest_negative: bool = False


@dataclass(frozen=True)
class ClassMetrics:
    cls: str
    n: int
    retrieval_hit_at_k: float | None = None
    overblock_rate: float | None = None
    abstain_correct_rate: float | None = None
    hallucination_rate: float | None = None
    raw_hallucination_rate: float | None = None


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
    overall_raw_hallucination_rate: float | None = None
    # How long an answer took: the median and the worst. The median says what the
    # thing costs; the maximum says whether one question is an outlier or the whole
    # corpus is slow — the two conclusions call for different fixes.
    generation_seconds_p50: float | None = None
    generation_seconds_max: float | None = None


def answer_is_honest_negative(answer: str | None) -> bool:
    """An explicit, plain "the files do not contain this" — the phrases are the
    product's own (``ABSENCE_PHRASES``), checked against the answer the person
    reads. Pure; the runner combines it with "and no hard grounding warnings"
    so an answer that says 'not found' while also inventing things never counts."""
    if not answer:
        return False
    from app.core.domain.rag_answer_evaluator import ABSENCE_PHRASES, visible_answer_text

    visible = visible_answer_text(answer).casefold()
    return any(phrase in visible for phrase in ABSENCE_PHRASES)


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


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[middle], 2)
    return round((ordered[middle - 1] + ordered[middle]) / 2, 2)


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
            _mean([1.0 if o.abstained else 0.0 for o in outs]) if cls in PROJECT_CLASSES else None
        )
        # For the abstain class, refusing is correct — and so is answering with an
        # explicit honest negative (see QuestionOutcome.honest_negative).
        abstain_correct = (
            _mean([1.0 if (o.abstained or o.honest_negative) else 0.0 for o in outs])
            if cls == CLASS_SHOULD_ABSTAIN
            else None
        )
        halluc = _mean([1.0 if o.hallucinated else 0.0 for o in outs if o.hallucinated is not None])
        raw_halluc = _mean(
            [1.0 if o.raw_hallucinated else 0.0 for o in outs if o.raw_hallucinated is not None]
        )

        per_class.append(
            ClassMetrics(
                cls=cls,
                n=len(cls_cases),
                retrieval_hit_at_k=hit,
                overblock_rate=overblock,
                abstain_correct_rate=abstain_correct,
                hallucination_rate=halluc,
                raw_hallucination_rate=raw_halluc,
            )
        )

    precise = [c for c in cases if c.cls == CLASS_PROJECT_PRECISE and c.id in by_id]
    project = [c for c in cases if c.cls in PROJECT_CLASSES and c.id in by_id]
    abstain = [c for c in cases if c.cls == CLASS_SHOULD_ABSTAIN and c.id in by_id]
    project_hallu = [
        by_id[c.id].hallucinated for c in project if by_id[c.id].hallucinated is not None
    ]
    project_raw_hallu = [
        by_id[c.id].raw_hallucinated for c in project if by_id[c.id].raw_hallucinated is not None
    ]
    timings = [o.generation_seconds for o in outcomes if o.generation_seconds is not None]

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
            [
                1.0 if (by_id[c.id].abstained or by_id[c.id].honest_negative) else 0.0
                for c in abstain
            ]
        ),
        overall_hallucination_rate=_mean([1.0 if h else 0.0 for h in project_hallu]),
        overall_raw_hallucination_rate=_mean([1.0 if h else 0.0 for h in project_raw_hallu]),
        generation_seconds_p50=_median(timings),
        generation_seconds_max=(round(max(timings), 2) if timings else None),
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
    lines.append(
        f"- Retrieval hit@{report.k} (precise): **{_pct(report.overall_retrieval_hit_at_k)}**"
    )
    lines.append(
        f"- Overblock rate (project qs wrongly abstained): **{_pct(report.overall_overblock_rate)}**"
    )
    lines.append(
        "- Should-abstain accuracy (refused, or an explicit honest negative): "
        f"**{_pct(report.overall_should_abstain_accuracy)}**"
    )
    if report.overall_hallucination_rate is not None:
        # The honest pair: the raw model's grounding-warning rate, then what
        # survives the app's corrective regeneration pass. The drop is the sieve
        # doing its job; equal numbers mean the sieve didn't fire on these cases.
        if report.overall_raw_hallucination_rate is not None:
            lines.append(
                "- Grounding-warning rate — raw model → after correction: "
                f"**{_pct(report.overall_raw_hallucination_rate)} → "
                f"{_pct(report.overall_hallucination_rate)}**"
            )
        else:
            lines.append(
                f"- Hallucination rate (generation): **{_pct(report.overall_hallucination_rate)}**"
            )
    if report.generation_seconds_p50 is not None:
        lines.append(
            "- Generation seconds — median / worst: "
            f"**{report.generation_seconds_p50:.1f}s / {report.generation_seconds_max:.1f}s**"
        )
    lines.append("")
    lines.append("## By class")
    lines.append("")
    lines.append("| Class | N | hit@k | overblock | abstain-correct | raw→halluc |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for cm in report.per_class:
        halluc_cell = (
            f"{_pct(cm.raw_hallucination_rate)}→{_pct(cm.hallucination_rate)}"
            if cm.raw_hallucination_rate is not None
            else _pct(cm.hallucination_rate)
        )
        lines.append(
            f"| {cm.cls} | {cm.n} | {_pct(cm.retrieval_hit_at_k)} | "
            f"{_pct(cm.overblock_rate)} | {_pct(cm.abstain_correct_rate)} | "
            f"{halluc_cell} |"
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
        if o.abstained:
            note = "abstained"
        elif o.honest_negative:
            note = "honest negative (answered: not in the files)"
        else:
            note = f"sources={list(o.source_paths)[:3]}"
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
            "raw_hallucination_rate": report.overall_raw_hallucination_rate,
            "generation_seconds_p50": report.generation_seconds_p50,
            "generation_seconds_max": report.generation_seconds_max,
        },
        "per_class": [
            {
                "cls": cm.cls,
                "n": cm.n,
                "retrieval_hit_at_k": cm.retrieval_hit_at_k,
                "overblock_rate": cm.overblock_rate,
                "abstain_correct_rate": cm.abstain_correct_rate,
                "hallucination_rate": cm.hallucination_rate,
                "raw_hallucination_rate": cm.raw_hallucination_rate,
            }
            for cm in report.per_class
        ],
        "questions": [
            {
                "id": o.question_id,
                "cls": by_case[o.question_id].cls if o.question_id in by_case else "?",
                "abstained": o.abstained,
                "honest_negative": o.honest_negative,
                "best_score": round(o.best_score, 4),
                "source_paths": list(o.source_paths),
                "hallucinated": o.hallucinated,
                "raw_hallucinated": o.raw_hallucinated,
                **(
                    {"generation_seconds": round(o.generation_seconds, 2)}
                    if o.generation_seconds is not None
                    else {}
                ),
                # Warning codes + answer text are only populated under --save-answers,
                # so flagged cases can be read by hand rather than trusted blind.
                **({"warning_codes": list(o.warning_codes)} if o.warning_codes else {}),
                **({"answer": o.answer} if o.answer is not None else {}),
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
