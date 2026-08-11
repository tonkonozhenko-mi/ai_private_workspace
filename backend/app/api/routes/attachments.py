"""Reading a file attached to a question.

The browser cannot open a Word document, a spreadsheet or a PDF — those are
containers, and JavaScript reading them as text produces mojibake. It used to
send that mojibake anyway, so the model answered from the filename and looked
like it had read a document it had never seen. The file now comes here, where
the same extractor the project index uses can read it, and where a format we
cannot read is refused in words rather than passed on as noise.

Base64 rather than a multipart upload: multipart would add python-multipart to a
bundle that is deliberately dependency-light, for a file that has already been
read into memory by the browser anyway.
"""

import base64
import binascii

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import document_extractor, file_system
from app.core.domain.document_extraction import MAX_DOCUMENT_BYTES
from app.core.use_cases.extract_attachment_text import ExtractAttachmentTextUseCase

router = APIRouter(prefix="/attachments", tags=["attachments"])

# Base64 inflates by 4/3; the cap is on the decoded bytes, so allow for that plus
# a little slack rather than rejecting a file that is actually within the limit.
_MAX_ENCODED_CHARS = (MAX_DOCUMENT_BYTES * 4) // 3 + 1024


class ExtractAttachmentTextRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_base64: str = Field(..., min_length=1, max_length=_MAX_ENCODED_CHARS)


class ExtractAttachmentTextResponse(BaseModel):
    filename: str
    file_type: str
    text: str
    truncated: bool
    # Set instead of text when the file could not be read, phrased for the person
    # who attached it. The UI shows it next to the file rather than attaching
    # anything, so "it read my document" is never silently untrue.
    skipped_reason: str | None = None


@router.post("/text", response_model=ExtractAttachmentTextResponse)
def extract_attachment_text(
    request: ExtractAttachmentTextRequest,
) -> ExtractAttachmentTextResponse:
    """Extract readable text from one attached file. Nothing is stored."""
    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The attachment could not be decoded.",
        ) from exc

    result = ExtractAttachmentTextUseCase(
        file_system=file_system,
        document_extractor=document_extractor,
    ).execute(request.filename, content)

    return ExtractAttachmentTextResponse(
        filename=result.filename,
        file_type=result.file_type,
        text=result.text,
        truncated=result.truncated,
        skipped_reason=result.skipped_reason,
    )
