"""Selective contextual enrichment (background, off by default).

Anthropic's *Contextual Retrieval* prepends a one-line "where does this chunk sit
in the document" note to each chunk before embedding, cutting failed retrievals
substantially. Doing it for *every* chunk needs an LLM call per chunk — hours on a
few thousand chunks on a local CPU, which the product's slow-hardware audience
can't spend. So this does it selectively and in the background:

- only the chunks that actually lose context when split — documentation prose that
  was cut mid-section, and *context-poor code fragments* (a length-split piece of a
  bigger file with no structural anchor like a heading or a ``def``/``class`` line,
  i.e. the orphans a hard split leaves behind);
- capped to a small fraction of the corpus so a big repo can't blow the budget;
- one chunk re-embedded at a time, so the index keeps working and just *gets
  smarter* as enrichment lands.

Everything here is pure and deterministic (selection, the cap, the prompt, and how
the enrichment is merged). Only the use case that drives it touches an LLM, the
embedder, and the vector store.

The enrichment is stored inline with a distinct ``[context: …]`` marker (separate
from the ``[source: …]`` provenance header), which doubles as the idempotency
signal: a chunk that already carries the marker is never enriched twice.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.chunking import chunk_section_label, strip_contextual_header

# Marker for the enrichment line. Distinct from the provenance header's
# ``[source: `` prefix so the two never collide and either can be detected or
# stripped independently. The enrichment line IS embedded (unlike the provenance
# header, which is stripped before embedding), because situating context is
# exactly what should steer the vector.
ENRICHMENT_PREFIX = "[context: "

# A situating note should be a short phrase, not a paragraph — cap it so a chatty
# model can't bloat the embedded text or drown the real content.
MAX_ENRICHMENT_CHARS = 240

# Safety valve so a large repo can't enrich its way through the whole corpus: never
# enrich more than this fraction of all chunks, nor more than this many in one run.
DEFAULT_MAX_FRACTION = 0.10
DEFAULT_MAX_CHUNKS = 200


@dataclass(frozen=True)
class EnrichmentCandidate:
    """A stored chunk considered for enrichment. ``content`` is the stored chunk
    (it may carry the ``[source: …]`` provenance header); ``file_type`` and
    ``position``/``total`` come from how it was indexed."""

    chunk_id: str
    source_path: str
    content: str
    file_type: str | None
    extension: str | None
    position: int
    total: int


def is_already_enriched(content: str) -> bool:
    """True when this chunk's body already carries an enrichment line, so it is
    never enriched a second time (idempotency without needing chunk metadata)."""
    return strip_contextual_header(content).lstrip().startswith(ENRICHMENT_PREFIX)


def chunk_qualifies_for_enrichment(candidate: EnrichmentCandidate) -> bool:
    """Deterministic rule for the two buckets worth enriching.

    A whole-file chunk (``total <= 1``) already has all of its own context, so it is
    never a candidate. Otherwise a chunk qualifies if it is either
    (a) documentation prose (markdown) cut into parts, or
    (b) a context-poor fragment of a larger file — no structural anchor (heading /
        ``def`` / ``class`` / block name) in its own text — which is the orphan a
        length-based hard split leaves behind.
    Already-enriched chunks are excluded.
    """
    if candidate.total <= 1:
        return False
    if is_already_enriched(candidate.content):
        return False
    if candidate.file_type == "markdown":
        return True
    body = strip_contextual_header(candidate.content)
    label = chunk_section_label(body, candidate.file_type, candidate.extension)
    return not label


def select_enrichment_targets(
    candidates: list[EnrichmentCandidate],
    *,
    corpus_size: int,
    max_fraction: float = DEFAULT_MAX_FRACTION,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[EnrichmentCandidate]:
    """Qualifying candidates, capped and in a stable order.

    The cap is the smaller of ``max_chunks`` and ``max_fraction`` of the whole
    corpus, so enrichment stays a small background top-up on any repo size. Ordering
    is by ``chunk_id`` so the same run always picks the same chunks (a later run
    continues where this one stopped, since enriched chunks drop out of the pool).
    """
    qualifying = [c for c in candidates if chunk_qualifies_for_enrichment(c)]
    qualifying.sort(key=lambda c: c.chunk_id)
    fraction_cap = int(max(0, corpus_size) * max_fraction)
    limit = min(max_chunks, fraction_cap) if corpus_size > 0 else max_chunks
    if limit <= 0:
        # A corpus too small for even one chunk under the fraction cap still gets a
        # floor of one, so tiny repos aren't shut out entirely.
        limit = 1
    return qualifying[:limit]


def build_enrichment_prompt(
    source_path: str,
    document_digest: str,
    chunk_body: str,
) -> str:
    """Prompt asking the model for a single situating sentence. Kept tight and
    output-only so a small local model doesn't ramble; the digest is whatever
    cheap framing the caller has (the document's first chunk, or a project
    summary)."""
    digest = document_digest.strip()
    digest_block = f"\nContext about the document:\n{digest}\n" if digest else "\n"
    return (
        "You are improving search for a code/document chunk. In ONE short sentence "
        "(no more than 25 words), say where this chunk sits and what it is about, so "
        "it can be found by a search query. Do not add quotes, labels, or commentary "
        "— output only the sentence.\n"
        f"\nFile: {source_path}\n"
        f"{digest_block}"
        f"\nChunk:\n{chunk_body}\n"
        "\nOne-sentence situating note:"
    )


def sanitize_enrichment(text: str) -> str:
    """Collapse a model's reply into a single clean line, capped in length. Returns
    an empty string when there's nothing usable, so the caller skips the chunk."""
    collapsed = " ".join(text.split())
    if not collapsed:
        return ""
    # If the model echoed the marker or a "note:" label, drop it.
    for lead in (ENRICHMENT_PREFIX, "context:", "note:", "situating note:"):
        if collapsed.lower().startswith(lead.lower()):
            collapsed = collapsed[len(lead) :].strip()
    if len(collapsed) > MAX_ENRICHMENT_CHARS:
        collapsed = collapsed[:MAX_ENRICHMENT_CHARS].rstrip()
    return collapsed


def apply_enrichment(original_content: str, enrichment: str) -> tuple[str, str]:
    """Merge a situating note into a stored chunk.

    Returns ``(stored_content, embed_text)``:
    - ``stored_content`` keeps the ``[source: …]`` provenance header (if any), then
      the ``[context: …]`` line, then the body — so display and citation still work
      and a re-run can detect the marker.
    - ``embed_text`` is the context line followed by the clean body (no provenance
      header), which is what should be embedded so the vector reflects both the
      situating note and the real content.
    """
    body = strip_contextual_header(original_content)
    header = original_content[: len(original_content) - len(body)]  # '' when no header
    context_line = f"{ENRICHMENT_PREFIX}{enrichment}]"
    stored_content = f"{header}{context_line}\n{body}"
    embed_text = f"{context_line}\n{body}"
    return stored_content, embed_text
