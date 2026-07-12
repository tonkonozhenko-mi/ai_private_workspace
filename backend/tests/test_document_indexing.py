"""Documents (Word/Excel/PDF/HTML) reach the index with a usable locator.

The fixtures are built here, in code, rather than committed as binaries: a .docx
and a .xlsx are just ZIPs of XML, so the test can write the minimum valid file and
stay readable — and there is no opaque blob in the repository.
"""

import zipfile
from pathlib import Path

import pytest

from app.adapters.documents.local_document_extractor import LocalDocumentExtractor
from app.adapters.filesystem.local_file_system import LocalFileSystem
from app.core.domain.document_extraction import EXTRACTABLE_DOCUMENT_TYPES
from app.core.use_cases.index_workspace import INDEXABLE_FILE_TYPES, IndexWorkspaceUseCase

_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
_DOCX_RELS = f"""<?xml version="1.0"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="{_REL_TYPE}" Target="word/document.xml"/>
</Relationships>"""

_DOCX_BODY = """<?xml version="1.0"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
  <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Production Runbook</w:t></w:r></w:p>
  <w:p><w:r><w:t>Deploys go through the staging cluster first.</w:t></w:r></w:p>
  <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>Rollback</w:t></w:r></w:p>
  <w:p><w:r><w:t>Run helm rollback payments to the previous revision.</w:t></w:r></w:p>
</w:body></w:document>"""

_XLSX_WORKBOOK = """<?xml version="1.0"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheets><sheet name="Costs" sheetId="1" r:id="rId1"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets>
</workbook>"""

_XLSX_SHARED = """<?xml version="1.0"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">
<si><t>Environment</t></si><si><t>Monthly cost USD</t></si>
<si><t>production</t></si><si><t>4200</t></si>
</sst>"""

_XLSX_SHEET = """<?xml version="1.0"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>
<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row>
</sheetData></worksheet>"""

_HTML_PAGE = """<html><head><title>Wiki</title></head><body>
<nav>Spaces | People | Powered by Confluence</nav>
<h1>Payments service</h1>
<p>The payments service handles card capture and refunds.</p>
<footer>Powered by Confluence</footer></body></html>"""


def _minimal_pdf(text: str) -> bytes:
    """A one-page PDF with a real text layer, assembled by hand (offsets and all)
    so the test needs no PDF-authoring library."""
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj" % number + body + b"endobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(out)


def _write_fixtures(root: Path) -> None:
    with zipfile.ZipFile(root / "runbook.docx", "w") as archive:
        archive.writestr("_rels/.rels", _DOCX_RELS)
        archive.writestr("word/document.xml", _DOCX_BODY)
    with zipfile.ZipFile(root / "costs.xlsx", "w") as archive:
        archive.writestr("xl/workbook.xml", _XLSX_WORKBOOK)
        archive.writestr("xl/sharedStrings.xml", _XLSX_SHARED)
        archive.writestr("xl/worksheets/sheet1.xml", _XLSX_SHEET)
    (root / "page.html").write_text(_HTML_PAGE, encoding="utf-8")
    (root / "notes.txt").write_text("The oncall rotation is weekly.", encoding="utf-8")
    (root / "adr.pdf").write_bytes(_minimal_pdf("Rollback runs helm rollback payments"))


def test_document_types_are_indexable():
    assert EXTRACTABLE_DOCUMENT_TYPES <= INDEXABLE_FILE_TYPES
    assert "plain_text" in INDEXABLE_FILE_TYPES


def test_scan_detects_document_types(tmp_path):
    _write_fixtures(tmp_path)
    detected = {f.path: f.detected_type for f in LocalFileSystem().list_files(str(tmp_path))}
    assert detected["runbook.docx"] == "word_document"
    assert detected["costs.xlsx"] == "excel_workbook"
    assert detected["page.html"] == "html"
    assert detected["notes.txt"] == "plain_text"
    assert detected["adr.pdf"] == "pdf_document"


def test_pdf_sections_are_addressed_by_page(tmp_path):
    # pypdf is a declared dependency, so CI always runs this. A developer whose
    # virtualenv predates it gets a skip with the reason, not a red failure.
    pytest.importorskip("pypdf", reason="pypdf is not installed in this environment")
    _write_fixtures(tmp_path)
    pdf = LocalDocumentExtractor().extract(str(tmp_path), "adr.pdf", "pdf_document")
    assert pdf.skipped_reason is None
    assert pdf.sections[0].locator == "page 1"
    assert "helm rollback" in pdf.sections[0].text


def test_extractor_returns_locators(tmp_path):
    _write_fixtures(tmp_path)
    extractor = LocalDocumentExtractor()

    docx = extractor.extract(str(tmp_path), "runbook.docx", "word_document")
    locators = [s.locator for s in docx.sections]
    assert 'heading path "Production Runbook > Rollback"' in locators
    assert any("helm rollback" in s.text for s in docx.sections)

    xlsx = extractor.extract(str(tmp_path), "costs.xlsx", "excel_workbook")
    assert xlsx.sections[0].locator == 'sheet "Costs" rows 2-2'
    assert "Monthly cost USD" in xlsx.sections[0].text  # header repeated in the block

    html = extractor.extract(str(tmp_path), "page.html", "html")
    body = "\n".join(s.text for s in html.sections)
    assert "card capture" in body
    assert "Powered by Confluence" not in body  # nav/footer chrome is dropped


def test_corrupt_document_is_skipped_with_a_reason(tmp_path):
    (tmp_path / "broken.docx").write_bytes(b"this is not a zip")
    result = LocalDocumentExtractor().extract(str(tmp_path), "broken.docx", "word_document")
    assert result.sections == []
    assert result.skipped_reason  # honest, and never raises


def test_xml_entity_bomb_in_a_document_is_refused(tmp_path):
    """A .docx is XML from an untrusted source. An entity-expansion bomb must be
    refused by the parser rather than expanded into gigabytes during a scan."""
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE d ['
        '<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(tmp_path / "bomb.docx", "w") as archive:
        archive.writestr("word/document.xml", bomb)

    result = LocalDocumentExtractor().extract(str(tmp_path), "bomb.docx", "word_document")
    assert result.sections == []
    assert result.skipped_reason


def test_chunks_carry_the_document_locator_in_their_header(tmp_path):
    _write_fixtures(tmp_path)
    use_case = IndexWorkspaceUseCase(
        workspace_repository=None,
        project_scan_repository=None,
        file_system=LocalFileSystem(),
        embedding_provider=None,
        vector_store=None,
        index_status_repository=None,
        document_extractor=LocalDocumentExtractor(),
    )
    scan = LocalFileSystem().list_files(str(tmp_path))
    runbook = next(f for f in scan if f.path == "runbook.docx")

    chunks, file_hash = use_case._chunks_for_file("ws-1", str(tmp_path), runbook)

    assert file_hash
    assert chunks
    headers = [c.content.splitlines()[0] for c in chunks]
    assert any(
        h.startswith('[source: runbook.docx › heading path "Production Runbook') for h in headers
    )


def test_document_without_an_extractor_is_simply_not_indexed(tmp_path):
    _write_fixtures(tmp_path)
    use_case = IndexWorkspaceUseCase(
        workspace_repository=None,
        project_scan_repository=None,
        file_system=LocalFileSystem(),
        embedding_provider=None,
        vector_store=None,
        index_status_repository=None,
    )
    scan = LocalFileSystem().list_files(str(tmp_path))
    runbook = next(f for f in scan if f.path == "runbook.docx")

    chunks, _ = use_case._chunks_for_file("ws-1", str(tmp_path), runbook)
    assert chunks == []
