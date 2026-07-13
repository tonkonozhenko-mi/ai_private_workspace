"""Extract text + locators from office documents on the local disk.

Deliberately dependency-light: ``.docx`` and ``.xlsx`` are OOXML — a ZIP of XML
parts — so they are read with ``zipfile`` plus a hardened ElementTree, and HTML
with ``html.parser``. That keeps two large packages out of the PyInstaller bundle.
Only PDF genuinely needs a library (``pypdf``); when it isn't installed we say so
rather than pretending the file is empty.

Nothing here touches the network — the whole point is that documents are read on
this computer and never leave it.
"""

from __future__ import annotations

import base64
import csv
import json
import logging
import re
import zipfile
import zlib
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

# A .docx/.xlsx is XML written by someone else's tool — or by someone hostile. The
# stdlib parser happily expands entities, which makes a "quadratic blowup" /
# billion-laughs document able to exhaust memory during a scan. defusedxml is the
# same ElementTree API with those features turned off.
from defusedxml.ElementTree import fromstring as parse_xml

from app.core.domain.document_extraction import (
    DIAGRAM,
    EXCEL_WORKBOOK,
    HTML_DOCUMENT,
    MAX_DOCUMENT_BYTES,
    MAX_PDF_PAGES,
    MAX_SHEET_ROWS,
    NOTEBOOK,
    PDF_DOCUMENT,
    PRESENTATION,
    TABULAR_DATA,
    WORD_DOCUMENT,
    ExtractedDocument,
    ExtractedSection,
    skipped,
)

logger = logging.getLogger(__name__)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
# PowerPoint keeps its words in DrawingML text runs (<a:t>), whatever shape holds them.
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_SLIDE_RE = re.compile(r"ppt/slides/slide(\d+)\.xml")


def _plain_text(value: str) -> str:
    """One line of collapsed text — draw.io labels arrive as little HTML fragments."""
    return " ".join(re.sub(r"<[^>]+>", " ", value).split())


# Rows per Excel chunk. The header row is repeated in every block: a chunk of bare
# numbers means nothing to an embedder (or a reader) without its column names.
_SHEET_ROWS_PER_SECTION = 20


def _no_heading(path: list[str]) -> str:
    return f'heading path "{" > ".join(path)}"' if path else "(no heading)"


def _markdown_table(rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    header, *body = rows
    width = len(header)
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * width) + "|"]
    lines += ["| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in body]
    return lines


def _row_block_sections(
    table: list[list[str]],
    locator: Callable[[int, int], str],
) -> list[ExtractedSection]:
    """Split a table into sections of `_SHEET_ROWS_PER_SECTION` rows, repeating the
    header in each one, and label each with `locator(first_row, last_row)` (1-based,
    row 1 being the header).

    Shared by the spreadsheet and the CSV path: a block of bare numbers means
    nothing — to an embedder or to a reader — without its column names, and that
    rule does not change with the file extension.
    """
    if not table:
        return []
    header, *body = table
    sections: list[ExtractedSection] = []
    for start in range(0, len(body), _SHEET_ROWS_PER_SECTION):
        block = body[start : start + _SHEET_ROWS_PER_SECTION]
        if not block:
            break
        text = "\n".join(_markdown_table([header, *block]))
        sections.append(ExtractedSection(locator(start + 2, start + 1 + len(block)), text))
    return sections


class LocalDocumentExtractor:
    """Adapter implementing DocumentTextExtractorPort. Never raises."""

    def extract(
        self,
        root_path: str,
        relative_path: str,
        file_type: str,
    ) -> ExtractedDocument:
        path = Path(root_path) / relative_path
        try:
            if not path.is_file():
                return skipped("The file could not be read.")
            size = path.stat().st_size
            if size > MAX_DOCUMENT_BYTES:
                mb = MAX_DOCUMENT_BYTES // (1024 * 1024)
                return skipped(f"The document is larger than {mb} MB and was not indexed.")

            if file_type == WORD_DOCUMENT:
                return self._docx(path)
            if file_type == EXCEL_WORKBOOK:
                return self._xlsx(path)
            if file_type == HTML_DOCUMENT:
                return self._html(path)
            if file_type == PDF_DOCUMENT:
                return self._pdf(path)
            if file_type == TABULAR_DATA:
                return self._csv(path)
            if file_type == NOTEBOOK:
                return self._notebook(path)
            if file_type == DIAGRAM:
                return self._drawio(path)
            if file_type == PRESENTATION:
                return self._pptx(path)
            return skipped(f"No extractor for '{file_type}'.")
        except zipfile.BadZipFile:
            # A .docx/.xlsx that isn't a valid OOXML container — often a renamed
            # legacy .doc/.xls. Say something the user can act on.
            return skipped(
                "The file is not a valid Word/Excel document (is it a legacy .doc/.xls?)."
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not fail the index
            logger.warning("document extraction failed path=%s: %s", relative_path, exc)
            return skipped("The document could not be read and was skipped.")

    # ------------------------------------------------------------------ .docx
    def _docx(self, path: Path) -> ExtractedDocument:
        with zipfile.ZipFile(path) as archive:
            if "word/document.xml" not in archive.namelist():
                return skipped("The Word document has no readable body.")
            body_xml = archive.read("word/document.xml")
        body = parse_xml(body_xml).find(f"{_W}body")
        if body is None:
            return skipped("The Word document has no readable body.")

        sections: list[ExtractedSection] = []
        heading_path: list[str] = []
        buffer: list[str] = []

        def flush() -> None:
            text = "\n".join(line for line in buffer if line.strip())
            if text.strip():
                sections.append(ExtractedSection(_no_heading(heading_path), text))
            buffer.clear()

        for element in body:
            if element.tag == f"{_W}p":
                style = element.find(f"{_W}pPr/{_W}pStyle")
                style_val = style.get(f"{_W}val") if style is not None else None
                text = "".join(t.text or "" for t in element.iter(f"{_W}t"))
                heading = re.fullmatch(r"Heading(\d)", style_val or "")
                if heading:
                    # A new heading closes the previous section and re-roots the
                    # path at its level, so "Deploy > Rollback" stays accurate.
                    flush()
                    level = int(heading.group(1))
                    del heading_path[level - 1 :]
                    if text.strip():
                        heading_path.append(text.strip())
                elif text.strip():
                    buffer.append(text)
            elif element.tag == f"{_W}tbl":
                rows = [
                    [
                        "".join(t.text or "" for t in cell.iter(f"{_W}t")).strip()
                        for cell in row.findall(f"{_W}tc")
                    ]
                    for row in element.findall(f"{_W}tr")
                ]
                buffer.extend(_markdown_table(rows))
        flush()

        if not sections:
            return skipped("The Word document contains no extractable text.")
        return ExtractedDocument(sections=sections)

    # ------------------------------------------------------------------ .xlsx
    def _xlsx(self, path: Path) -> ExtractedDocument:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            shared: list[str] = []
            if "xl/sharedStrings.xml" in names:
                root = parse_xml(archive.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(t.text or "" for t in si.iter(f"{_S}t")) for si in root.iter(f"{_S}si")
                ]

            sheet_names: list[str] = []
            if "xl/workbook.xml" in names:
                wb = parse_xml(archive.read("xl/workbook.xml"))
                sheet_names = [s.get("name") or "" for s in wb.iter(f"{_S}sheet")]

            parts = sorted(n for n in names if n.startswith("xl/worksheets/sheet"))
            sections: list[ExtractedSection] = []
            truncated = False

            for index, part in enumerate(parts):
                sheet = sheet_names[index] if index < len(sheet_names) else f"Sheet{index + 1}"
                root = parse_xml(archive.read(part))
                table: list[list[str]] = []
                for row in root.iter(f"{_S}row"):
                    if len(table) >= MAX_SHEET_ROWS:
                        truncated = True
                        break
                    cells = []
                    for cell in row.findall(f"{_S}c"):
                        value = cell.find(f"{_S}v")
                        raw = (value.text or "") if value is not None else ""
                        if cell.get("t") == "s" and raw.isdigit() and int(raw) < len(shared):
                            raw = shared[int(raw)]
                        cells.append(raw.strip())
                    if any(cells):
                        table.append(cells)
                if not table:
                    continue

                sections += _row_block_sections(
                    table, lambda a, b, sheet=sheet: f'sheet "{sheet}" rows {a}-{b}'
                )

        if not sections:
            return skipped("The workbook contains no extractable rows.")
        if truncated:
            logger.info("xlsx truncated at %d rows path=%s", MAX_SHEET_ROWS, path.name)
        return ExtractedDocument(sections=sections)

    # --------------------------------------------------------------- .csv/.tsv
    def _csv(self, path: Path) -> ExtractedDocument:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        table: list[list[str]] = []
        truncated = False
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            for row in csv.reader(handle, delimiter=delimiter):
                if len(table) >= MAX_SHEET_ROWS:
                    truncated = True
                    break
                cells = [cell.strip() for cell in row]
                if any(cells):
                    table.append(cells)

        if len(table) < 2:
            return skipped("The file has no data rows below its header.")
        if truncated:
            logger.info("csv truncated at %d rows path=%s", MAX_SHEET_ROWS, path.name)
        return ExtractedDocument(sections=_row_block_sections(table, lambda a, b: f"rows {a}-{b}"))

    # ----------------------------------------------------------------- .ipynb
    def _notebook(self, path: Path) -> ExtractedDocument:
        """Markdown and code cells in order, addressed by cell number.

        Outputs are deliberately left out: they are re-runnable noise, and a single
        plot is megabytes of base64 that would drown the notebook's actual words.
        """
        try:
            notebook = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return skipped("The notebook is not valid JSON and was skipped.")
        if not isinstance(notebook, dict):
            return skipped("The notebook has no readable cells.")

        sections: list[ExtractedSection] = []
        for number, cell in enumerate(notebook.get("cells") or [], start=1):
            if not isinstance(cell, dict):
                continue
            kind = cell.get("cell_type")
            if kind not in {"markdown", "code"}:
                continue
            source = cell.get("source") or ""
            text = ("".join(source) if isinstance(source, list) else str(source)).strip()
            if not text:
                continue
            # Fence the code so the chunker and the reader can both tell prose
            # from program.
            body = f"```\n{text}\n```" if kind == "code" else text
            sections.append(ExtractedSection(f"cell {number}", body))

        if not sections:
            return skipped("The notebook has no readable cells.")
        return ExtractedDocument(sections=sections)

    # ------------------------------------------------------------------ .html
    def _html(self, path: Path) -> ExtractedDocument:
        parser = _HtmlSections()
        parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
        parser.flush()
        if not parser.sections:
            return skipped("The page contains no extractable text.")
        return ExtractedDocument(sections=parser.sections)

    # ---------------------------------------------------------------- .drawio
    def _drawio(self, path: Path) -> ExtractedDocument:
        """A diagram, read as the words on it.

        A .drawio file is XML: every box and every arrow carries a ``value`` — its
        label. Those labels *are* the architecture ("Ingestion" → "Ledger layer" →
        "PowerBI"), and they are exactly what someone asks about. The pixels stay
        unread; the names do not.

        draw.io usually stores each page deflate-compressed inside <diagram>, so the
        raw text looks like base64 noise. Both forms are handled.
        """
        raw = path.read_text(encoding="utf-8", errors="ignore")
        try:
            root = parse_xml(raw)
        except Exception:  # noqa: BLE001 - a corrupt diagram is skipped, not fatal
            return skipped("The diagram could not be read.")

        pages = root.findall(".//diagram") or [root]
        sections: list[ExtractedSection] = []
        for index, page in enumerate(pages, start=1):
            model = self._drawio_model(page)
            if model is None:
                continue
            labels = [
                label
                for cell in model.iter("mxCell")
                if (label := _plain_text(cell.get("value") or ""))
            ]
            # Shapes carry their label on mxCell; some stencils put it on the parent
            # <object> element instead, where it is the "label" attribute.
            labels += [
                label
                for obj in model.iter("object")
                if (label := _plain_text(obj.get("label") or ""))
            ]
            if not labels:
                continue
            name = page.get("name") if page.tag == "diagram" else None
            locator = f'page "{name}"' if name else f"page {index}"
            sections.append(ExtractedSection(locator, "\n".join(dict.fromkeys(labels))))

        if not sections:
            return skipped("The diagram has no labelled shapes to read.")
        return ExtractedDocument(sections=sections)

    @staticmethod
    def _drawio_model(page):  # noqa: ANN001, ANN205 - Element, kept untyped like the rest
        """The <mxGraphModel> of a diagram page, decompressing it when needed."""
        model = page.find(".//mxGraphModel")
        if model is not None:
            return model
        payload = (page.text or "").strip()
        if not payload:
            return None
        try:
            # draw.io's own encoding: deflate (raw, no zlib header), base64, URL-escaped.
            inflated = zlib.decompress(base64.b64decode(payload), -zlib.MAX_WBITS)
            return parse_xml(unquote(inflated.decode("utf-8")))
        except Exception:  # noqa: BLE001 - an unreadable page is skipped, not fatal
            return None

    # ------------------------------------------------------------------ .pptx
    def _pptx(self, path: Path) -> ExtractedDocument:
        """Slides, one section per slide — the same OOXML trick as Word and Excel."""
        with zipfile.ZipFile(path) as archive:
            slide_names = sorted(
                (n for n in archive.namelist() if _SLIDE_RE.fullmatch(n)),
                key=lambda n: int(_SLIDE_RE.fullmatch(n).group(1)),  # type: ignore[union-attr]
            )
            sections: list[ExtractedSection] = []
            for name in slide_names:
                number = int(_SLIDE_RE.fullmatch(name).group(1))  # type: ignore[union-attr]
                slide = parse_xml(archive.read(name))
                # <a:t> is the text run — the only element that holds words, whether
                # they sit in a title, a bullet, a table cell or a shape.
                lines = [
                    line for node in slide.iter(f"{_A}t") if (line := _plain_text(node.text or ""))
                ]
                if lines:
                    sections.append(ExtractedSection(f"slide {number}", "\n".join(lines)))

        if not sections:
            return skipped("The presentation contains no readable text.")
        return ExtractedDocument(sections=sections)

    # ------------------------------------------------------------------- .pdf
    def _pdf(self, path: Path) -> ExtractedDocument:
        try:
            from pypdf import PdfReader  # noqa: PLC0415 - optional, imported on use
        except ImportError:
            return skipped("PDF support needs the 'pypdf' package, which isn't installed.")

        reader = PdfReader(str(path))
        pages = reader.pages
        if len(pages) > MAX_PDF_PAGES:
            return skipped(f"The PDF has more than {MAX_PDF_PAGES} pages and was not indexed.")

        sections: list[ExtractedSection] = []
        for number, page in enumerate(pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception as exc:  # noqa: BLE001 - a bad page shouldn't lose the good ones
                logger.warning("pdf page %d of %s could not be read: %s", number, path.name, exc)
                continue
            if text:
                sections.append(ExtractedSection(f"page {number}", text))

        if not sections:
            # Every page is an image: this is a scan. Indexing nothing silently
            # would make the document look searched-but-empty; say why instead.
            return skipped(
                "The PDF has no text layer (it looks scanned); OCR is not supported yet."
            )
        return ExtractedDocument(sections=sections)


class _HtmlSections(HTMLParser):
    """Text + heading path from HTML, with the page chrome thrown away.

    A Confluence space export wraps the content in navigation, scripts and a
    footer; indexing those would put "Powered by Confluence" into every answer.
    """

    _SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "title", "head"}
    _HEADING = re.compile(r"h([1-6])")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[ExtractedSection] = []
        self._heading_path: list[str] = []
        self._buffer: list[str] = []
        self._skip_depth = 0
        self._heading_level: int | None = None
        self._heading_text: list[str] = []

    def flush(self) -> None:
        text = "\n".join(line for line in self._buffer if line.strip())
        if text.strip():
            self.sections.append(ExtractedSection(_no_heading(self._heading_path), text))
        self._buffer.clear()

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif self._HEADING.fullmatch(tag):
            self.flush()
            self._heading_level = int(tag[1])
            self._heading_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif self._HEADING.fullmatch(tag) and self._heading_level:
            title = " ".join("".join(self._heading_text).split())
            del self._heading_path[self._heading_level - 1 :]
            if title:
                self._heading_path.append(title)
            self._heading_level = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._heading_level:
            self._heading_text.append(data)
        elif data.strip():
            self._buffer.append(" ".join(data.split()))
