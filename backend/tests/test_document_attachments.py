"""Documentation folders: attachments, diagrams and decks.

Documentation is never one file. Whatever tool produced it — a browser saving a
Confluence page, Word's "Save as Web Page", Notion, Typora — you end up with a
document and a folder of its assets beside it. Before this, that folder was a heap:
the diagram nobody could cite, the spreadsheet nobody could place, and the saver's
own stylesheet indexed as if it were documentation.
"""

import base64
import zipfile
import zlib
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from app.adapters.documents.local_document_extractor import LocalDocumentExtractor
from app.core.domain.companion_assets import (
    document_title,
    is_saver_chrome,
    origin_note,
    owning_document,
)
from app.core.domain.document_extraction import DIAGRAM, PRESENTATION

_DRAWIO_MODEL = (
    "<mxGraphModel><root>"
    '<mxCell id="1" value="Ingestion layer"/>'
    '<mxCell id="2" value="&lt;b&gt;Silver layer&lt;/b&gt;"/>'
    '<mxCell id="3" value="writes to" edge="1"/>'
    '<object id="4" label="PowerBI"/>'
    "</root></mxGraphModel>"
)


def _plain_drawio(path: Path) -> None:
    path.write_text(f'<mxfile><diagram name="Flow">{_DRAWIO_MODEL}</diagram></mxfile>')


def _compressed_drawio(path: Path) -> None:
    """The form draw.io actually saves: deflate → base64 → URL-escaped."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    packed = compressor.compress(quote(_DRAWIO_MODEL).encode()) + compressor.flush()
    payload = base64.b64encode(packed).decode()
    path.write_text(f'<mxfile><diagram name="Flow">{payload}</diagram></mxfile>')


def _pptx(path: Path, slides: list[list[str]]) -> None:
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    with zipfile.ZipFile(path, "w") as archive:
        for number, lines in enumerate(slides, start=1):
            runs = "".join(f"<a:p><a:r><a:t>{escape(line)}</a:t></a:r></a:p>" for line in lines)
            archive.writestr(
                f"ppt/slides/slide{number}.xml",
                f'<p:sld xmlns:p="{p}" xmlns:a="{a}"><p:cSld><p:spTree>{runs}'
                "</p:spTree></p:cSld></p:sld>",
            )


# --------------------------------------------------------- the companion folder


def test_an_attachment_is_attributed_to_the_document_it_illustrates():
    known = {"[ADR-08]._Sequence_generation.html", "notes/Design.md"}
    assert (
        owning_document("[ADR-08]._Sequence_generation_files/silver layer.drawio", known)
        == "[ADR-08]._Sequence_generation.html"
    )
    # Not one tool's layout: Typora's ".assets", pandoc's "_media", Word's "_files".
    assert owning_document("notes/Design.assets/diagram.png", known) == "notes/Design.md"


def test_the_attribution_is_stated_in_words_a_person_can_check():
    known = {"[ADR-08]._Sequence_generation.html"}
    note = origin_note("[ADR-08]._Sequence_generation_files/silver layer.drawio", known)
    assert note == 'attachment of "[ADR-08] Sequence generation"'
    assert document_title("[DMD-1]_Ref_Static_Data.html") == "[DMD-1] Ref Static Data"


def test_an_ordinary_project_file_has_no_such_story_to_tell():
    assert owning_document("src/app.py", {"src/app.py"}) is None
    assert origin_note("src/app.py", {"src/app.py"}) is None


def test_a_folder_that_only_looks_like_one_is_left_alone():
    """ "_files" with no document beside it was never a companion folder."""
    assert (
        owning_document("archive_files/report.xlsx", known_paths={"archive_files/report.xlsx"})
        is None
    )


def test_the_savers_own_stylesheets_are_not_documentation():
    assert is_saver_chrome("Page_files/style.css")
    assert is_saver_chrome("Page_files/fonts/aui.woff2")
    assert not is_saver_chrome("Page_files/costs.xlsx")
    # A stylesheet the person keeps in their own project is theirs.
    assert not is_saver_chrome("src/styles/main.css")


# -------------------------------------------------------------------- diagrams


def test_a_diagram_is_read_as_the_words_on_it(tmp_path: Path):
    path = tmp_path / "silver layer.drawio"
    _plain_drawio(path)
    document = LocalDocumentExtractor().extract(str(tmp_path), path.name, DIAGRAM)
    text = document.full_text()
    assert "Ingestion layer" in text
    assert "Silver layer" in text  # the label is an HTML fragment; the markup is dropped
    assert "writes to" in text  # arrows are labelled too, and the labels are the flow
    assert "PowerBI" in text  # some shapes carry their label on the parent <object>
    assert document.sections[0].locator == 'page "Flow"'


def test_a_diagram_saved_the_way_drawio_actually_saves_it(tmp_path: Path):
    """draw.io deflates and base64s each page: read naively, the file is noise."""
    path = tmp_path / "compressed.drawio"
    _compressed_drawio(path)
    document = LocalDocumentExtractor().extract(str(tmp_path), path.name, DIAGRAM)
    assert "Ingestion layer" in document.full_text()


def test_a_diagram_with_no_labels_says_so_instead_of_pretending(tmp_path: Path):
    path = tmp_path / "blank.drawio"
    path.write_text(
        '<mxfile><diagram name="Empty"><mxGraphModel><root>'
        '<mxCell id="1"/></root></mxGraphModel></diagram></mxfile>'
    )
    document = LocalDocumentExtractor().extract(str(tmp_path), path.name, DIAGRAM)
    assert document.sections == []
    assert document.skipped_reason


# ----------------------------------------------------------------------- decks


def test_a_deck_is_read_one_slide_at_a_time(tmp_path: Path):
    path = tmp_path / "review.pptx"
    _pptx(path, [["Q3 review", "Ingestion is late"], ["Next quarter", "Cut scope"]])
    document = LocalDocumentExtractor().extract(str(tmp_path), path.name, PRESENTATION)
    assert [section.locator for section in document.sections] == ["slide 1", "slide 2"]
    assert "Ingestion is late" in document.sections[0].text
    assert "Cut scope" in document.sections[1].text


# ----------------------------------------------------------------- the scan


def test_the_scan_knows_a_documentation_folder_when_it_sees_one(tmp_path: Path):
    """End to end over a real folder: the page, its diagram and its picture are
    recognised; the browser's stylesheet is not."""
    from app.adapters.filesystem.local_file_system import LocalFileSystem

    (tmp_path / "Design_files").mkdir()
    (tmp_path / "Design.html").write_text("<h1>Design</h1><p>The silver layer.</p>")
    _plain_drawio(tmp_path / "Design_files" / "silver layer.drawio")
    (tmp_path / "Design_files" / "diagram.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "Design_files" / "style.css").write_text("body{margin:0}")
    _pptx(tmp_path / "Review.pptx", [["Q3"]])

    types = {
        file.path: file.detected_type
        for file in LocalFileSystem().list_files(str(tmp_path), respect_gitignore=False)
    }
    assert types["Design.html"] == "html"
    assert types["Design_files/silver layer.drawio"] == "diagram"
    assert types["Review.pptx"] == "presentation"
    # Known, but honestly not indexable: we cannot read a picture without OCR.
    assert types["Design_files/diagram.png"] == "image"
    # The browser's own stylesheet is not documentation.
    assert types["Design_files/style.css"] == "unknown"
