"""Office documents as indexable text.

A project folder rarely contains only code: runbooks live in Word, cost sheets in
Excel, architecture decisions in PDF, and a Confluence space export is a pile of
HTML. Those are binary/markup containers — reading them as UTF-8 text yields
garbage — so they need extraction before the normal chunk → embed → cite pipeline
can touch them.

The unit of extraction is a *section* with a human-readable **locator**: the place
a reader would have to open to check the claim ("page 12", "sheet 'Costs' rows
2-21", "heading path 'Deploy > Rollback'"). The locator flows into the chunk's
provenance header, so a grounded answer cites *where in the document*, not just
which file — which is the whole point of citing a 90-page PDF.

Extraction is honest about what it cannot do: a scanned PDF has no text layer, an
oversized workbook is refused rather than silently truncated, and a corrupt file
is skipped with a reason instead of failing the whole index.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# File types that must go through a DocumentTextExtractor instead of read_text.
# Plain text (.txt/.rst) is deliberately NOT here — it is already text, and the
# ordinary read_text + structure-aware chunker handle it.
WORD_DOCUMENT = "word_document"
EXCEL_WORKBOOK = "excel_workbook"
PDF_DOCUMENT = "pdf_document"
HTML_DOCUMENT = "html"
PLAIN_TEXT = "plain_text"

EXTRACTABLE_DOCUMENT_TYPES: frozenset[str] = frozenset(
    {WORD_DOCUMENT, EXCEL_WORKBOOK, PDF_DOCUMENT, HTML_DOCUMENT}
)

# Guard rails. A single monster file must not stall a scan or blow up memory; we
# refuse it loudly (the reason reaches the index status) instead of hanging.
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_PDF_PAGES = 300
MAX_SHEET_ROWS = 10_000


@dataclass(frozen=True)
class ExtractedSection:
    """One addressable piece of a document.

    ``locator`` is written for a human who wants to verify the citation — it is
    shown in the chunk header, e.g. ``[source: docs/runbook.pdf › page 12]``.
    """

    locator: str
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    """The result of extracting one file.

    ``skipped_reason`` set (with no sections) means "we deliberately did not index
    this, and here is what to tell the user" — a scanned PDF, an oversized file, a
    format we don't support, or a corrupt container.
    """

    sections: list[ExtractedSection] = field(default_factory=list)
    skipped_reason: str | None = None

    @property
    def is_empty(self) -> bool:
        return not any(s.text.strip() for s in self.sections)

    def full_text(self) -> str:
        """All section text joined — used for the content hash that drives
        incremental re-indexing. Hashing the *extracted text* (not the raw bytes)
        means re-saving a document without changing its words does not force a
        re-embed."""
        return "\n\n".join(s.text for s in self.sections)


def skipped(reason: str) -> ExtractedDocument:
    return ExtractedDocument(sections=[], skipped_reason=reason)
