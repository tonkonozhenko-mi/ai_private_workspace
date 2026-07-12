"""Port: turn a binary/markup document on disk into locatable text sections.

Keeps the parsing libraries (and their quirks) out of the core: the use case only
knows "give me sections with locators", the adapter decides how a .docx or .pdf
is taken apart.
"""

from __future__ import annotations

from typing import Protocol

from app.core.domain.document_extraction import ExtractedDocument


class DocumentTextExtractorPort(Protocol):
    def extract(
        self,
        root_path: str,
        relative_path: str,
        file_type: str,
    ) -> ExtractedDocument:
        """Extract text sections from one document.

        Must never raise: a corrupt or unsupported file comes back as an
        ExtractedDocument with ``skipped_reason`` set, so one bad file cannot
        fail the whole index.
        """
        ...
