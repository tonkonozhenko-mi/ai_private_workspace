"""Turn a file attached to a question into text the model can actually read.

The project index already knows how to do this. The point of this use case is
that attaching a file now goes through the same extractor and — importantly —
the same file-type classification, rather than a second opinion about what a
``.docx`` is. The file is written to a temporary directory and classified by
walking it, which is literally the code path a scan uses, so a format the index
can read is a format an attachment can read, by construction.
"""

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.core.domain.attachment_text import legacy_format_refusal, looks_like_text
from app.core.domain.document_extraction import (
    EXTRACTABLE_DOCUMENT_TYPES,
    IMAGE,
    MAX_DOCUMENT_BYTES,
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
        safe_name = Path(filename or "attachment").name or "attachment"

        if len(content) > MAX_DOCUMENT_BYTES:
            return self._skipped(
                safe_name,
                f"The file is larger than {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB "
                "and was not read.",
            )

        refusal = legacy_format_refusal(safe_name)
        if refusal is not None:
            # Named before anything is written to disk: these formats are not
            # broken files, they are formats we do not read, and the person can
            # act on that in ten seconds.
            return self._skipped(safe_name, refusal)

        with tempfile.TemporaryDirectory(prefix="attachment-") as work_dir:
            path = Path(work_dir) / safe_name
            path.write_bytes(content)
            file_type = self._classify(work_dir, safe_name)

            if file_type == IMAGE:
                return self._skipped(
                    safe_name,
                    "Images are read by the vision model — attach it as an image instead.",
                    file_type=file_type,
                )

            if file_type in EXTRACTABLE_DOCUMENT_TYPES:
                document = self.document_extractor.extract(work_dir, safe_name, file_type)
                if document.skipped_reason:
                    return self._skipped(safe_name, document.skipped_reason, file_type=file_type)
                if document.is_empty:
                    return self._skipped(
                        safe_name,
                        "The document has no text to read — a scan or a set of images, perhaps.",
                        file_type=file_type,
                    )
                return self._trimmed(safe_name, file_type, document.full_text())

            # Everything else is read as text, which is what it is. The guard is
            # for a binary format nobody has named: its bytes decoded as
            # characters are noise, and noise that reaches the model looks like
            # an answer afterwards.
            if not looks_like_text(content[:8192]):
                return self._skipped(
                    safe_name,
                    "This does not look like a text file, so it was not read.",
                    file_type=file_type,
                )
            return self._trimmed(
                safe_name, file_type, self.file_system.read_text_file(work_dir, safe_name)
            )

    def _classify(self, work_dir: str, safe_name: str) -> str:
        """The scan's own answer to "what kind of file is this".

        Asking the walker rather than re-deriving it from the extension is the
        whole point: one classifier, so an attachment and an indexed file of the
        same type are never treated differently.
        """
        try:
            for file in self.file_system.list_files(work_dir, respect_gitignore=False):
                if file.path == safe_name:
                    return file.detected_type
        except Exception as exc:  # noqa: BLE001 - classification must not fail the request
            logger.warning("attachment classification failed name=%s: %s", safe_name, exc)
        return "unknown"

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
