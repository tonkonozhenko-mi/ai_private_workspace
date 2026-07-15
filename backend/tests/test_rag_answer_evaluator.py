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
    answer = (
        'Here is the config:\n\n```hcl\nregion = "eu-central-1"\nprofile = "prod"\n```\n(main.tf)'
    )
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


def test_howto_shell_block_is_not_flagged_as_quote() -> None:
    warnings = evaluate_rag_answer(
        question="How do I deploy the infrastructure?",
        answer="Run the following:\n\n```bash\nterraform init && terraform apply -auto-approve\n```",
        sources=[_source("README.md")],
        source_contents=["# Project\n\nSee the deploy docs for details."],
    )
    assert not any(w.code == "quote_not_in_sources" for w in warnings)


def test_shell_block_still_flagged_when_not_howto() -> None:
    # Not a how-to question → a fenced block claiming to be from the files is
    # still verified.
    warnings = evaluate_rag_answer(
        question="What commands are defined in the makefile?",
        answer="The file contains:\n\n```bash\nmake sacrifice && make ascend\n```",
        sources=[_source("Makefile")],
        source_contents=["build:\n\tgo build ./..."],
    )
    assert any(w.code == "quote_not_in_sources" for w in warnings)


def test_howto_non_shell_block_is_still_verified() -> None:
    warnings = evaluate_rag_answer(
        question="How do I set the region?",
        answer='Set it here:\n\n```hcl\nregion = "invented-region-zzz-1" profile prod\n```',
        sources=[_source("main.tf")],
        source_contents=['region = "eu-central-1"'],
    )
    assert any(w.code == "quote_not_in_sources" for w in warnings)


def test_bracketed_wiki_filenames_are_read_whole_not_truncated() -> None:
    # Wiki exports name pages "[ADR-02]_Invoice_numbering.md" — brackets are part
    # of the filename. The first prose-pattern excluded them and truncated the
    # token to "_Invoice_numbering.md", which matched nothing, so every honest
    # wiki answer citing its own page was flagged as inventing a file
    # (2026-07-15: wiki-export halluc 9.1% → 54.5% from this alone).
    warnings = evaluate_rag_answer(
        question="How are invoice numbers issued?",
        answer=(
            "From a per-tenant sequence — see "
            "[[ADR-02] Invoice numbering]([ADR-02]_Invoice_numbering.md)."
        ),
        sources=[_source("wiki/[ADR-02]_Invoice_numbering.md")],
        source_contents=["# [ADR-02] Invoice numbering\n\nPer-tenant sequence."],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def test_a_cross_linked_wiki_page_counts_as_read_not_invented() -> None:
    warnings = evaluate_rag_answer(
        question="Where are implementation notes?",
        answer="In [[Capability] Invoicing]([Capability]_Invoicing.md).",
        sources=[_source("wiki/[ADR-02]_Invoice_numbering.md")],
        source_contents=[
            "Implementation notes live in [[Capability] Invoicing]([Capability]_Invoicing.md)."
        ],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def test_invented_prose_filenames_are_still_flagged_after_the_bracket_fix() -> None:
    warnings = evaluate_rag_answer(
        question="Where is storage configured?",
        answer="Storage is configured in backend/.env and docker-compose.yml.",
        sources=[_source("wiki/[ADR-08]_Report_storage_v2.md")],
        source_contents=["Statements are stored in object storage."],
    )
    evidence = _warning_by_code(warnings, "answer_cited_unknown_source").evidence
    assert "backend/.env" in evidence and "docker-compose.yml" in evidence


def test_the_prompts_citation_example_is_the_evaluators_placeholder() -> None:
    # The prompt used to demonstrate citing with `main.tf`; small models echoed
    # the example into answers, one invented "main.tf in the Terraform directory"
    # for a project with no Terraform — seeded by our own instruction. The example
    # is now an obvious placeholder, the evaluator ignores exactly it, and the
    # prompt is built FROM the constant so the two cannot drift apart.
    from app.core.domain.rag_answer_evaluator import CITATION_EXAMPLE_PATH
    from app.core.domain.rag_prompt import build_workspace_question_prompt

    prompt = build_workspace_question_prompt("q?", [])
    assert CITATION_EXAMPLE_PATH in prompt
    warnings = evaluate_rag_answer(
        question="q?",
        answer=f"Cite files like `{CITATION_EXAMPLE_PATH}` (README.md).",
        sources=[_source("README.md")],
        source_contents=["# Readme"],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def test_a_backticked_sentence_is_not_a_filename_claim() -> None:
    warnings = evaluate_rag_answer(
        question="How is isolation enforced?",
        answer=(
            "`Row-level isolation with a mandatory tenant_id "
            "(wiki/[ADR-04]_Tenant_isolation.md)` (wiki/[ADR-04]_Tenant_isolation.md)"
        ),
        sources=[_source("wiki/[ADR-04]_Tenant_isolation.md")],
        source_contents=["Row-level isolation with a mandatory tenant_id."],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def test_a_bare_directory_in_backticks_is_not_a_filename_claim() -> None:
    warnings = evaluate_rag_answer(
        question="Where do the pages live?",
        answer="Pages live under `wiki/` (MANIFEST.md).",
        sources=[_source("MANIFEST.md")],
        source_contents=["# wiki-export corpus"],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def test_a_name_broken_at_a_space_anchors_to_the_retrieved_path() -> None:
    # "[ADR-01] Service split.md" — the model writes the page TITLE plus .md; the
    # tokenizer keeps the tail "split.md". A retrieved path ending with that tail
    # is what the model was reaching for, not an invention.
    warnings = evaluate_rag_answer(
        question="What should I read first?",
        answer="Read [ADR-01] Service split.md first (wiki/[ADR-01]_Service_split.md).",
        sources=[_source("wiki/[ADR-01]_Service_split.md")],
        source_contents=["# [ADR-01] Service split"],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def test_a_fuller_address_for_a_page_the_evidence_links_is_not_invented() -> None:
    # The retrieved page links "([ADR-01]_Service_split.md)"; the model answers
    # with "wiki/[ADR-01]_Service_split.md" — same file, fuller address.
    warnings = evaluate_rag_answer(
        question="What should I read first?",
        answer="Start with wiki/[ADR-01]_Service_split.md ([Onboarding]_Start_here.md).",
        sources=[_source("wiki/[Onboarding]_Start_here.md")],
        source_contents=["Read [[ADR-01] Service split]([ADR-01]_Service_split.md) first."],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def test_grounding_judges_the_answer_the_person_reads_not_the_draft() -> None:
    # qwen3-style output: inline deliberation closed by </think>, then the real
    # answer. The draft echoes the prompt's citation placeholder and quotes chunks
    # loosely — judging it flagged three clean wiki answers (2026-07-15).
    draft = 'We check `path/to/file.py`... the text says "something loosely quoted here"...'
    final = (
        "Isolation uses a mandatory `tenant_id` on every table (wiki/[ADR-04]_Tenant_isolation.md)."
    )
    warnings = evaluate_rag_answer(
        question="How is isolation enforced?",
        answer=f"{draft}</think>{final}",
        sources=[_source("wiki/[ADR-04]_Tenant_isolation.md")],
        source_contents=["Row-level isolation with a mandatory tenant_id on every table."],
    )
    assert warnings == []


def test_citing_a_retrieved_source_path_is_not_an_ungrounded_term() -> None:
    # A page does not contain its own filename; flagging the citation the prompt
    # asked for as a fabricated "term" punished obedience.
    warnings = evaluate_rag_answer(
        question="What should I read first?",
        answer="Start with `wiki/[Onboarding]_Start_here.md`.",
        sources=[_source("wiki/[Onboarding]_Start_here.md")],
        source_contents=["Read ADR-01 first."],
    )
    assert not any(w.code == "answer_term_not_in_context" for w in warnings)


def test_parentheses_inside_backticks_are_punctuation_not_part_of_the_name() -> None:
    warnings = evaluate_rag_answer(
        question="Where do I start?",
        answer="See `(wiki/[Onboarding]_Start_here.md)` for the reading order.",
        sources=[_source("wiki/[Onboarding]_Start_here.md")],
        source_contents=["Read ADR-01 first."],
    )
    assert not any(w.code == "answer_cited_unknown_source" for w in warnings)


def _source(source_path: str) -> RagSource:
    return RagSource(
        chunk_id=f"{source_path}-1",
        source_path=source_path,
        score=1.0,
        preview="preview",
    )


def _warning_by_code(warnings, code: str):
    return next(warning for warning in warnings if warning.code == code)
