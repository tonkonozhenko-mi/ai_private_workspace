"""A document attached to a question must actually be read.

Live on 0.7.10: a Word file dropped into the chat produced an answer that
paraphrased its title and nothing else. Asked what was inside, the model
answered about a different file entirely. It looked like it had stopped
understanding; in fact it had never been given the document.

The browser had read the file with `slice.text()` — bytes decoded as UTF-8. For
a .docx (a ZIP) or a legacy .doc (an OLE container) that yields mojibake, and
mojibake is what was sent. The extractor that reads Word, Excel, slides and PDF
for the project index was right there, and the attachment path never called it.

These tests use the real endpoint and real files, because the interesting part
is the seam: classification, extraction, and what is said when neither works.
"""

import base64
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post(filename: str, content: bytes):
    return client.post(
        "/attachments/text",
        json={
            "filename": filename,
            "content_base64": base64.b64encode(content).decode("ascii"),
        },
    )


def _docx(paragraphs: list[str]) -> bytes:
    """A real .docx: the minimum OOXML the extractor reads."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        f'<?xml version="1.0"?><w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def test_a_word_document_comes_back_as_its_words():
    content = _docx(
        [
            "Questionnaire - NON EU countries - Blue Card",
            "Question 1: state your current country of residence.",
        ]
    )

    body = _post("Questionnaire.docx", content).json()

    assert body["skipped_reason"] is None
    assert "current country of residence" in body["text"]
    assert body["file_type"] == "word_document"


def test_the_first_question_is_answerable_from_the_text_not_the_filename():
    """The exact failure: the answer described the document by its title. That is
    all a filename can tell you, and it is what you get when the body never
    arrives."""
    content = _docx(["Blue Card questionnaire", "Question 1: your passport number."])

    body = _post("Questionnaire- NON EU countries - Blue Card.docx", content).json()

    assert "passport number" in body["text"]


def test_a_legacy_doc_is_refused_in_words_a_person_can_act_on():
    # Previously this was read as UTF-8 and its noise was sent to the model.
    body = _post("runbook.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1 legacy OLE bytes").json()

    assert body["text"] == ""
    assert "Word 97" in body["skipped_reason"]
    # Not "unsupported file": it says what to do about it.
    assert ".docx" in body["skipped_reason"]


def test_a_docx_that_is_not_really_a_docx_says_so():
    body = _post("renamed.docx", b"this was a .doc that somebody renamed").json()

    assert body["text"] == ""
    assert body["skipped_reason"]


def test_a_plain_text_file_still_goes_straight_through():
    body = _post("notes.txt", "ЖУРАВЛЬ-77 is the codeword.".encode()).json()

    assert body["skipped_reason"] is None
    assert "ЖУРАВЛЬ-77" in body["text"]


def test_a_csv_keeps_its_header_row():
    body = _post("costs.csv", b"service,monthly\nrds,1200\ns3,40\n").json()

    assert body["skipped_reason"] is None
    assert "monthly" in body["text"]


def test_binary_nobody_named_is_not_passed_off_as_text():
    # The last line of defence. Noise reaching the model is worse than a refusal,
    # because afterwards it looks like an answer.
    body = _post("mystery.bin", bytes(range(256)) * 8).json()

    assert body["text"] == ""
    assert body["skipped_reason"]


def test_an_oversized_file_is_refused_rather_than_half_read():
    body = _post("huge.txt", b"x" * (21 * 1024 * 1024))

    # Either the schema's cap or the use case's — both are honest refusals, and
    # neither silently truncates the person's document.
    assert body.status_code in {400, 422} or body.json()["skipped_reason"]


def test_undecodable_base64_is_a_clear_400():
    response = client.post(
        "/attachments/text",
        json={"filename": "x.txt", "content_base64": "not base64 at all!!!"},
    )

    assert response.status_code == 400


def test_a_filename_cannot_choose_where_the_file_lands(tmp_path):
    """A filename arrives from the browser, where "../../.ssh/id_rsa" is a name
    like any other. CodeQL flagged exactly this path (py/path-injection) once the
    extractor gained a caller whose relative path is not from a directory walk."""
    body = _post("../../escaped.txt", b"harmless").json()

    assert body["filename"] == "escaped.txt"
    assert not (tmp_path.parent / "escaped.txt").exists()


def test_the_extractor_refuses_a_path_that_leaves_its_root(tmp_path):
    """The boundary lives at the point that opens the file, not in whichever
    caller remembered to sanitise. Checked directly, because the endpoint's own
    basename() would otherwise be the only thing standing between a name and the
    filesystem — and one guard in one caller is how this class of bug survives."""
    from app.adapters.documents.local_document_extractor import LocalDocumentExtractor

    secret = tmp_path / "secret.csv"
    secret.write_text("column\nvalue\n", encoding="utf-8")
    root = tmp_path / "work"
    root.mkdir()

    escaped = LocalDocumentExtractor().extract(str(root), "../secret.csv", "tabular_data")

    assert escaped.sections == []
    assert escaped.skipped_reason


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
