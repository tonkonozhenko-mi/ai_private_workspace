"""Pure rules for selective background enrichment: which chunks qualify, the cap,
the prompt, and how a situating note is merged for storage vs. embedding."""

from app.core.domain.chunking import build_contextual_chunk
from app.core.domain.contextual_enrichment import (
    ENRICHMENT_PREFIX,
    MAX_ENRICHMENT_CHARS,
    EnrichmentCandidate,
    apply_enrichment,
    build_enrichment_prompt,
    chunk_qualifies_for_enrichment,
    is_already_enriched,
    sanitize_enrichment,
    select_enrichment_targets,
)


def _candidate(
    chunk_id="ws:doc.md:1",
    source_path="doc.md",
    content="some body",
    file_type="markdown",
    extension="md",
    position=2,
    total=3,
) -> EnrichmentCandidate:
    return EnrichmentCandidate(
        chunk_id=chunk_id,
        source_path=source_path,
        content=content,
        file_type=file_type,
        extension=extension,
        position=position,
        total=total,
    )


def test_whole_file_chunk_never_qualifies():
    # total == 1 → the chunk already holds all of its own context.
    assert not chunk_qualifies_for_enrichment(_candidate(total=1, position=1))


def test_multipart_markdown_qualifies():
    assert chunk_qualifies_for_enrichment(_candidate(file_type="markdown", total=3))


def test_code_fragment_without_a_structural_anchor_qualifies():
    # A mid-file Python fragment with no def/class/heading in its own text.
    frag = _candidate(
        source_path="app/util.py",
        content="    total += line_value(x)\n    results.append(total)\n",
        file_type="python",
        extension="py",
        total=5,
    )
    assert chunk_qualifies_for_enrichment(frag)


def test_code_chunk_with_a_definition_does_not_qualify():
    frag = _candidate(
        source_path="app/util.py",
        content="def compute(x):\n    return x + 1\n",
        file_type="python",
        extension="py",
        total=5,
    )
    assert not chunk_qualifies_for_enrichment(frag)


def test_already_enriched_chunk_is_skipped():
    enriched_body = f"{ENRICHMENT_PREFIX}already situated]\nsome body"
    assert is_already_enriched(enriched_body)
    assert not chunk_qualifies_for_enrichment(_candidate(content=enriched_body))


def test_qualification_ignores_the_provenance_header():
    # A real stored chunk carries a [source: …] header; qualification must look at
    # the body beneath it, not be fooled by the header line.
    stored = build_contextual_chunk(
        "    total += 1\n    keep_going()\n",
        source_path="app/util.py",
        position=2,
        total=4,
        file_type="python",
        extension="py",
    )
    assert chunk_qualifies_for_enrichment(
        _candidate(content=stored, file_type="python", extension="py", total=4)
    )


def test_selection_caps_by_fraction_and_is_stable():
    cands = [
        _candidate(chunk_id=f"ws:doc.md:{i}", file_type="markdown", total=50) for i in range(50)
    ]
    # 10% of 50 = 5.
    picked = select_enrichment_targets(cands, corpus_size=50, max_fraction=0.10, max_chunks=200)
    assert len(picked) == 5
    # Stable order by chunk_id (string sort: :0, :1, :10, :11, …).
    assert [c.chunk_id for c in picked] == sorted(c.chunk_id for c in cands)[:5]


def test_selection_caps_by_max_chunks():
    cands = [
        _candidate(chunk_id=f"ws:doc.md:{i}", file_type="markdown", total=999) for i in range(999)
    ]
    picked = select_enrichment_targets(cands, corpus_size=999, max_fraction=0.9, max_chunks=3)
    assert len(picked) == 3


def test_selection_floor_of_one_for_a_tiny_corpus():
    # A corpus so small the fraction cap rounds to zero still gets a single chunk.
    cands = [_candidate(chunk_id="ws:doc.md:1", file_type="markdown", total=2)]
    picked = select_enrichment_targets(cands, corpus_size=2, max_fraction=0.10, max_chunks=200)
    assert len(picked) == 1


def test_selection_excludes_non_qualifying():
    good = _candidate(chunk_id="ws:a.md:1", file_type="markdown", total=3)
    whole = _candidate(chunk_id="ws:b.md:0", file_type="markdown", total=1)
    picked = select_enrichment_targets([good, whole], corpus_size=2)
    assert [c.chunk_id for c in picked] == ["ws:a.md:1"]


def test_prompt_mentions_path_digest_and_asks_for_one_sentence():
    prompt = build_enrichment_prompt("app/api/main.py", "A payments API service.", "def health():")
    assert "app/api/main.py" in prompt
    assert "A payments API service." in prompt
    assert "ONE short sentence" in prompt
    assert "def health():" in prompt


def test_prompt_without_a_digest_is_still_valid():
    prompt = build_enrichment_prompt("x.py", "", "body")
    assert "x.py" in prompt and "body" in prompt


def test_sanitize_collapses_whitespace_and_strips_echoed_labels():
    assert sanitize_enrichment("  This  situates\nthe   chunk.  ") == "This situates the chunk."
    assert sanitize_enrichment("context: part of the ledger worker") == "part of the ledger worker"
    assert sanitize_enrichment(f"{ENRICHMENT_PREFIX}echoed marker") == "echoed marker"
    assert sanitize_enrichment("   ") == ""


def test_sanitize_caps_length():
    out = sanitize_enrichment("word " * 200)
    assert len(out) <= MAX_ENRICHMENT_CHARS


def test_apply_enrichment_with_a_provenance_header():
    stored_original = build_contextual_chunk(
        "return x + 1\n",
        source_path="app/util.py",
        position=2,
        total=4,
        file_type="python",
        extension="py",
    )
    stored, embed = apply_enrichment(stored_original, "helper that increments a value")
    # Stored keeps the [source: …] header, then the [context: …] line, then body.
    assert stored.startswith("[source: ")
    assert f"\n{ENRICHMENT_PREFIX}helper that increments a value]\nreturn x + 1" in stored
    # Embedded text drops the provenance header but leads with the context line.
    assert embed.startswith(f"{ENRICHMENT_PREFIX}helper that increments a value]\n")
    assert "[source: " not in embed
    assert embed.endswith("return x + 1\n")


def test_apply_enrichment_without_a_header():
    stored, embed = apply_enrichment("bare body\n", "situating note")
    assert stored == f"{ENRICHMENT_PREFIX}situating note]\nbare body\n"
    assert embed == stored


def test_apply_enrichment_output_is_detected_as_enriched():
    stored, _ = apply_enrichment("body", "note")
    assert is_already_enriched(stored)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
