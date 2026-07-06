"""Pure metric scoring for the golden-set harness."""

from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
    QuestionCase,
    golden_set,
)
from eval.harness import (
    QuestionOutcome,
    case_is_hit,
    compute_report,
    render_markdown,
    report_to_dict,
)


def _precise(qid, paths):
    return QuestionCase(qid, "q?", CLASS_PROJECT_PRECISE, tuple(paths))


def test_case_is_hit_matches_path_substring():
    case = _precise("x", ("core/domain/parent_document.py",))
    hit = QuestionOutcome("x", False, ("backend/app/core/domain/parent_document.py",), 0.7)
    miss = QuestionOutcome("x", False, ("backend/app/core/domain/mmr.py",), 0.7)
    assert case_is_hit(case, hit) is True
    assert case_is_hit(case, miss) is False


def test_report_metrics_by_class():
    cases = [
        _precise("p1", ("a.py",)),
        _precise("p2", ("b.py",)),
        QuestionCase("b1", "about?", CLASS_PROJECT_BROAD),
        QuestionCase("s1", "what time is it?", CLASS_SHOULD_ABSTAIN),
        QuestionCase("s2", "hello", CLASS_SHOULD_ABSTAIN),
    ]
    outcomes = [
        QuestionOutcome("p1", False, ("src/a.py",), 0.8),  # hit
        QuestionOutcome("p2", True, (), 0.1),  # abstained → overblock + miss
        QuestionOutcome("b1", False, ("src/readme.md",), 0.6),  # grounded, ok
        QuestionOutcome("s1", False, ("src/x.py",), 0.5),  # wrongly grounded (bad)
        QuestionOutcome("s2", True, (), 0.05),  # correctly abstained
    ]
    report = compute_report("nomic", 5, cases, outcomes)

    # precise: 1/2 hit; 1/2 abstained (overblock)
    assert report.overall_retrieval_hit_at_k == 0.5
    # project overblock over p1,p2,b1 → only p2 abstained → 1/3
    assert report.overall_overblock_rate == round(1 / 3, 4)
    # should-abstain accuracy: s1 wrong, s2 right → 1/2
    assert report.overall_should_abstain_accuracy == 0.5
    # no generation → hallucination None
    assert report.overall_hallucination_rate is None


def test_hallucination_rate_when_generation_present():
    cases = [_precise("p1", ("a.py",)), _precise("p2", ("b.py",))]
    outcomes = [
        QuestionOutcome("p1", False, ("src/a.py",), 0.8, hallucinated=True),
        QuestionOutcome("p2", False, ("src/b.py",), 0.7, hallucinated=False),
    ]
    report = compute_report("qwen3", 5, cases, outcomes)
    assert report.overall_hallucination_rate == 0.5


def test_raw_vs_product_hallucination_pair():
    # Two answers flagged on the raw model; the corrective pass rescues one → the
    # product rate is half the raw rate. This is the sieve-working headline.
    cases = [_precise("p1", ("a.py",)), _precise("p2", ("b.py",))]
    outcomes = [
        QuestionOutcome("p1", False, ("src/a.py",), 0.8, hallucinated=True, raw_hallucinated=True),
        QuestionOutcome("p2", False, ("src/b.py",), 0.7, hallucinated=False, raw_hallucinated=True),
    ]
    report = compute_report("qwen3", 5, cases, outcomes)
    assert report.overall_raw_hallucination_rate == 1.0
    assert report.overall_hallucination_rate == 0.5
    md = render_markdown(report, cases, outcomes)
    assert "100.0% → 50.0%" in md  # raw → after-correction pair shown
    d = report_to_dict(report, cases, outcomes)
    assert d["overall"]["raw_hallucination_rate"] == 1.0
    assert d["questions"][0]["raw_hallucinated"] is True


def test_save_answers_fields_only_present_when_populated():
    cases = [_precise("p1", ("a.py",))]
    # With answer + codes recorded (the --save-answers path):
    saved = [
        QuestionOutcome(
            "p1",
            False,
            ("src/a.py",),
            0.8,
            hallucinated=False,
            raw_hallucinated=False,
            warning_codes=("answer_missing_source_paths",),
            answer="Because the config sets it.",
        )
    ]
    d = report_to_dict(compute_report("nomic", 5, cases, saved), cases, saved)
    q = d["questions"][0]
    assert q["answer"] == "Because the config sets it."
    assert q["warning_codes"] == ["answer_missing_source_paths"]
    # Without them (default run), the keys are omitted, keeping reports small:
    plain = [QuestionOutcome("p1", False, ("src/a.py",), 0.8, hallucinated=False)]
    q2 = report_to_dict(compute_report("nomic", 5, cases, plain), cases, plain)["questions"][0]
    assert "answer" not in q2
    assert "warning_codes" not in q2


def test_render_markdown_and_dict_are_wellformed():
    cases = [_precise("p1", ("a.py",)), QuestionCase("s1", "hi", CLASS_SHOULD_ABSTAIN)]
    outcomes = [
        QuestionOutcome("p1", True, (), 0.1),  # a failure (abstained on precise)
        QuestionOutcome("s1", True, (), 0.05),  # correct
    ]
    report = compute_report("bge-m3", 5, cases, outcomes)
    md = render_markdown(report, cases, outcomes)
    assert "Golden-set eval" in md and "bge-m3" in md
    assert "`p1`" in md  # the failure is listed
    d = report_to_dict(report, cases, outcomes)
    assert d["embedder"] == "bge-m3"
    assert d["overall"]["should_abstain_accuracy"] == 1.0
    assert len(d["questions"]) == 2


def test_golden_set_is_wellformed():
    gs = golden_set()
    assert len(gs) >= 40
    ids = [c.id for c in gs]
    assert len(ids) == len(set(ids))  # unique ids
    # every precise case labels at least one expected path; abstain cases none
    for c in gs:
        if c.cls == CLASS_PROJECT_PRECISE:
            assert c.expected_paths, c.id
        if c.cls == CLASS_SHOULD_ABSTAIN:
            assert c.should_abstain
    # Fable's live regression is present
    assert any("time" in c.question.lower() and c.cls == CLASS_SHOULD_ABSTAIN for c in gs)
