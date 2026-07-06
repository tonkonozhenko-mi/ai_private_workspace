from app.core.domain.rag import RagSource
from app.core.domain.rag_answer_evaluator import evaluate_rag_answer


def test_empty_answer_with_sources_creates_high_warning() -> None:
    warnings = evaluate_rag_answer(
        question="How is the backend configured?",
        answer="",
        sources=[_source("main.tf")],
        source_contents=['terraform { backend "s3" {} }'],
    )

    warning = _warning_by_code(warnings, "empty_answer_with_sources")
    assert warning.severity == "high"
    assert warning.evidence == ["main.tf"]


def test_answer_claiming_no_context_despite_sources_creates_high_warning() -> None:
    warnings = evaluate_rag_answer(
        question="How is the backend configured?",
        answer="No indexed context was found.",
        sources=[_source("main.tf")],
        source_contents=['terraform { backend "s3" {} }'],
    )

    warning = _warning_by_code(
        warnings,
        "answer_claims_no_context_despite_sources",
    )
    assert warning.severity == "high"


def test_answer_missing_source_paths_creates_medium_warning() -> None:
    warnings = evaluate_rag_answer(
        question="How is the backend configured?",
        answer="The Terraform backend uses S3.",
        sources=[_source("main.tf")],
        source_contents=['terraform { backend "s3" {} }'],
    )

    warning = _warning_by_code(warnings, "answer_missing_source_paths")
    assert warning.severity == "medium"
    assert warning.evidence == ["main.tf"]


def test_absence_phrase_conflict_creates_low_warning() -> None:
    warnings = evaluate_rag_answer(
        question="Which region is configured?",
        answer="There is no direct mention of region (terragrunt.hcl).",
        sources=[_source("terragrunt.hcl")],
        source_contents=['region = "eu-central-1"'],
    )

    warning = _warning_by_code(warnings, "possible_absence_claim_conflict")
    assert warning.severity == "low"
    assert "region" in warning.evidence[0]


def test_grounded_answer_with_source_path_has_no_warnings() -> None:
    warnings = evaluate_rag_answer(
        question="Which region is configured?",
        answer="The configured region is eu-central-1 (terragrunt.hcl).",
        sources=[_source("terragrunt.hcl")],
        source_contents=['region = "eu-central-1"'],
    )

    assert warnings == []


def test_quote_not_in_sources_flags_invented_double_quote() -> None:
    warnings = evaluate_rag_answer(
        question="What does the readme say about setup?",
        answer='The docs state "run the sacred bootstrap ritual before deploy" clearly.',
        sources=[_source("README.md")],
        source_contents=["# Setup\n\nRun `make install` then `make dev` to start."],
    )

    warning = _warning_by_code(warnings, "quote_not_in_sources")
    assert warning.severity == "review"
    assert "sacred bootstrap ritual" in warning.evidence[0]


def test_quote_present_verbatim_is_not_flagged() -> None:
    warnings = evaluate_rag_answer(
        question="How do I start the app?",
        answer='The README says "Run make install then make dev to start" (README.md).',
        sources=[_source("README.md")],
        source_contents=["# Setup\n\nRun make install then make dev to start the app."],
    )

    assert not any(w.code == "quote_not_in_sources" for w in warnings)


def test_quote_check_normalizes_whitespace_across_lines() -> None:
    # The code block reflows the source's single line; normalization should match.
    answer = "Here is the config:\n\n```hcl\nregion = \"eu-central-1\"\nprofile = \"prod\"\n```\n(main.tf)"
    warnings = evaluate_rag_answer(
        question="What is the config?",
        answer=answer,
        sources=[_source("main.tf")],
        source_contents=['region = "eu-central-1"   profile = "prod"'],
    )
    assert not any(w.code == "quote_not_in_sources" for w in warnings)


def test_short_quotes_are_ignored() -> None:
    warnings = evaluate_rag_answer(
        question="What region?",
        answer='It uses "us-east-1" region.',
        sources=[_source("main.tf")],
        source_contents=['region = "eu-central-1"'],
    )
    # "us-east-1" is under the 20-char verbatim threshold → not flagged as a quote.
    assert not any(w.code == "quote_not_in_sources" for w in warnings)


def _source(source_path: str) -> RagSource:
    return RagSource(
        chunk_id=f"{source_path}-1",
        source_path=source_path,
        score=1.0,
        preview="preview",
    )


def _warning_by_code(warnings, code: str):
    return next(warning for warning in warnings if warning.code == code)
