"""Retrieval-quality eval harness: pure scorer + the run use case."""

from types import SimpleNamespace

from app.core.domain.answer_eval import EvalCase, aggregate, score_case
from app.core.use_cases.run_retrieval_eval import (
    RunRetrievalEvalInput,
    RunRetrievalEvalUseCase,
)

# -- pure scorer ------------------------------------------------------------


def test_score_case_source_recall_and_suffix_match():
    case = EvalCase(question="db?", expect_sources=["db/config.tf", "README.md"])
    # "db/config.tf" matched exactly; "README.md" matched as a suffix of a path.
    score = score_case(case, ["app/db/config.tf", "docs/README.md", "x.py"])
    assert score.source_recall == 1.0
    assert score.passed is True
    assert set(score.matched_sources) == {"db/config.tf", "README.md"}


def test_score_case_partial_recall_fails():
    case = EvalCase(question="q", expect_sources=["a.tf", "b.tf"])
    score = score_case(case, ["a.tf"])
    assert score.source_recall == 0.5
    assert score.passed is False


def test_score_case_keywords_in_answer():
    case = EvalCase(question="q", expect_sources=["a.tf"], expect_keywords=["Postgres", "ASN"])
    score = score_case(case, ["a.tf"], answer_text="It uses postgres with the correct asn.")
    assert score.keyword_hits == 2
    assert score.passed is True
    missed = score_case(case, ["a.tf"], answer_text="It uses postgres.")
    assert missed.keyword_hits == 1 and missed.passed is False


def test_aggregate_report():
    scores = [
        score_case(EvalCase("q1", ["a.tf"]), ["a.tf"]),
        score_case(EvalCase("q2", ["b.tf"]), ["x.tf"]),
    ]
    report = aggregate(scores)
    assert report.total == 2 and report.passed == 1
    assert report.pass_rate == 0.5
    assert report.source_recall == 0.5


# -- run use case over a fake index -----------------------------------------


class _WSRepo:
    def get(self, wid):
        return SimpleNamespace(id=wid) if wid == "w1" else None


class _Embed:
    provider_name = "fake"
    model_name = "fake"

    def embed_text(self, text):
        return [1.0, 0.0]


class _Vector:
    """Returns a result whose source_path encodes the query, so we can assert
    the eval wired retrieval per case."""

    def search(self, *, query_text, **kw):
        path = "db/config.tf" if "database" in query_text.lower() else "other.txt"
        return [
            SimpleNamespace(chunk_id="c", source_path=path, content="x", score=0.9, metadata={})
        ]


def test_run_retrieval_eval_scores_per_case():
    uc = RunRetrievalEvalUseCase(_WSRepo(), _Embed(), _Vector())
    report = uc.execute(
        RunRetrievalEvalInput(
            workspace_id="w1",
            cases=[
                EvalCase(
                    question="where is the database configured", expect_sources=["db/config.tf"]
                ),
                EvalCase(question="something unrelated", expect_sources=["db/config.tf"]),
            ],
        )
    )
    assert report.total == 2
    assert report.passed == 1  # first hits db/config.tf, second doesn't


# -- negative / abstain cases + hallucination metric ------------------------


def test_abstain_case_passes_when_retrieval_not_confident():
    case = EvalCase(question="unrelated thing", expect_abstain=True)
    # Top similarity below the threshold → system would correctly abstain.
    score = score_case(case, ["whatever.txt"], top_score=0.10)
    assert score.passed is True
    assert score.abstained is True


def test_abstain_case_fails_when_retrieval_is_confident():
    case = EvalCase(question="unrelated thing", expect_abstain=True)
    # High similarity → it would feed confident (wrong) context and likely fabricate.
    score = score_case(case, ["whatever.txt"], top_score=0.95)
    assert score.passed is False
    assert score.abstained is False


def test_aggregate_reports_hallucination_rate():
    scores = [
        score_case(EvalCase("pos", ["a.tf"]), ["a.tf"], top_score=0.9),
        score_case(EvalCase("neg1", expect_abstain=True), ["x"], top_score=0.1),  # abstained ✓
        score_case(EvalCase("neg2", expect_abstain=True), ["y"], top_score=0.9),  # leaked ✗
    ]
    report = aggregate(scores)
    assert report.abstain_total == 2
    assert report.abstain_correct == 1
    assert report.hallucination_rate == 0.5
    # Positive-case recall unaffected by the negative cases.
    assert report.source_recall == 1.0


# -- safety overblock metric (v0.3.x) ---------------------------------------


def test_overblock_rate_counts_wrongly_refused_positives():
    # Positive case whose top similarity is below the abstain threshold → the
    # safeguards would refuse it even though the sources were retrieved.
    blocked = score_case(EvalCase("db?", expect_sources=["db.tf"]), ["db.tf"], top_score=0.10)
    fine = score_case(EvalCase("db?", expect_sources=["db.tf"]), ["db.tf"], top_score=0.90)
    assert blocked.overblocked is True
    assert fine.overblocked is False
    report = aggregate([blocked, fine])
    assert report.overblock_rate == 0.5
