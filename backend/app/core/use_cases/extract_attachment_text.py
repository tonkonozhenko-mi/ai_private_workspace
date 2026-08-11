"""Turn a file attached to a question into text the model can actually read.

The project index has always known how to read Word, Excel, slides and PDF; the
attachment path did not, and sent the browser's UTF-8 reading of a ZIP instead.
This use case puts the two on the same extractor.

One rule shapes the code more than anything else: **the filename never reaches
the filesystem.** It arrives from a browser, where "../../.ssh/id_rsa" is a name
like any other, and sanitising such a name is a thing you can get right and
still be one refactor away from getting wrong. So the name is used for exactly
one purpose — deciding what kind of document this is, by matching its extension
against a table — and what lands on disk is a literal from that table. There is
no path here built from anything a person typed.
"""

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.domain.attachment_text import legacy_format_refusal, looks_like_text
from app.core.domain.document_extraction import (
    MAX_DOCUMENT_BYTES,
    PLAIN_TEXT,
    PLAIN_TEXT_ATTACHMENT_NAME,
    attachment_document_type,
)

logger = logging.getLogger(__name__)

# How much extracted text one attachment may contribute. The prompt budget is
# shared with the project's own sources, and a 90-page PDF would evict them all.
MAX_ATTACHMENT_CHARACTERS = 40_000


@dataclass(frozen=True)
class AttachmentText:
    filename: str
    file_type: str
    text: str
    truncated: bool
    # Set when there is no text to give: the reason, written for the person who
    # attached the file. Never both this and text.
    skipped_reason: str | None = None


class ExtractAttachmentTextUseCase:
    def __init__(self, file_system, document_extractor) -> None:
        self.file_system = file_system
        self.document_extractor = document_extractor

    def execute(self, filename: str, content: bytes) -> AttachmentText:
        # Kept only to say it back to the person; it is never used as a path.
        label = (filename or "attachment").strip() or "attachment"

        if len(content) > MAX_DOCUMENT_BYTES:
            return self._skipped(
                label,
                f"The file is larger than {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB "
                "and was not read.",
            )

        refusal = legacy_format_refusal(label)
        if refusal is not None:
            # Named before anything is written: these are formats we do not read,
            # not broken files, and the person can act on that in ten seconds.
            return self._skipped(label, refusal)

        document = attachment_document_type(label)
        if document is None and not looks_like_text(content[:8192]):
            # Not a document we extract, and its bytes are not words either.
            # Noise reaching the model is worse than a refusal, because
            # afterwards it looks like an answer.
            return self._skipped(label, "This does not look like a text file, so it was not read.")

        file_type, disk_name = document or (PLAIN_TEXT, PLAIN_TEXT_ATTACHMENT_NAME)

        with tempfile.TemporaryDirectory(prefix="attachment-") as work_dir:
            # Both halves are ours: a temporary directory this process just made,
            # and a name from the table above.
            Path(work_dir).joinpath(disk_name).write_bytes(content)

            if file_type == PLAIN_TEXT:
                return self._trimmed(
                    label, file_type, self.file_system.read_text_file(work_dir, disk_name)
                )

            extracted = self.document_extractor.extract(work_dir, disk_name, file_type)
            if extracted.skipped_reason:
                return self._skipped(label, extracted.skipped_reason, file_type=file_type)
            if extracted.is_empty:
                return self._skipped(
                    label,
                    "The document has no text to read — a scan or a set of images, perhaps.",
                    file_type=file_type,
                )
            return self._trimmed(label, file_type, extracted.full_text())

    @staticmethod
    def _skipped(filename: str, reason: str, file_type: str = "unknown") -> AttachmentText:
        return AttachmentText(
            filename=filename,
            file_type=file_type,
            text="",
            truncated=False,
            skipped_reason=reason,
        )

    @staticmethod
    def _trimmed(filename: str, file_type: str, text: str) -> AttachmentText:
        body = text or ""
        truncated = len(body) > MAX_ATTACHMENT_CHARACTERS
        return AttachmentText(
            filename=filename,
            file_type=file_type,
            text=body[:MAX_ATTACHMENT_CHARACTERS],
            truncated=truncated,
        )
