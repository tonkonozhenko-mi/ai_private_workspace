from app.core.domain.rag import RagSource
from app.core.domain.rag_answer_evaluator import (
    evaluate_rag_answer,
    find_unsupported_citations,
)


def test_flags_file_cited_but_not_in_context():
    bad = find_unsupported_citations(
        "The backend uses `main.tf` and also `made_up.yaml`.",
        ["main.tf"],
    )
    assert bad == ["made_up.yaml"]


def test_basename_matches_full_path():
    bad = find_unsupported_citations(
        "See `backend.tf`.",
        ["infra/prod/backend.tf"],
    )
    assert bad == []


def test_ignores_non_file_identifiers():
    bad = find_unsupported_citations(
        "It uses `terraform` and an `S3` bucket and the `region` variable.",
        ["main.tf"],
    )
    assert bad == []


def test_path_separator_token_flagged():
    bad = find_unsupported_citations("Config is in `k8s/overlays/prod`.", ["main.tf"])
    assert bad == ["k8s/overlays/prod"]


def test_evaluator_emits_warning_for_unknown_citation():
    sources = [RagSource(chunk_id="c1", source_path="main.tf", score=1.0, preview="")]
    warnings = evaluate_rag_answer(
        question="how is the backend configured?",
        answer="The backend is in `main.tf`, and secrets in `vault.hcl`.",
        sources=sources,
        source_contents=["terraform backend s3"],
    )
    codes = {w.code for w in warnings}
    assert "answer_cited_unknown_source" in codes
    bad_evidence = next(w.evidence for w in warnings if w.code == "answer_cited_unknown_source")
    assert "vault.hcl" in bad_evidence
