"""Extract text + locators from office documents on the local disk.

Deliberately dependency-light: ``.docx`` and ``.xlsx`` are OOXML — a ZIP of XML
parts — so ``zipfile`` + ``xml.etree`` read them with no third-party library, and
HTML with ``html.parser``. That keeps two large packages out of the PyInstaller
bundle. Only PDF genuinely needs a library (``pypdf``); when it isn't installed we
say so rather than pretending the file is empty.

Nothing here touches the network — the whole point is that documents are read on
this computer and never leave it.
"""

from __future__ import annotations

import logging
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from app.core.domain.document_extraction import (
    EXCEL_WORKBOOK,
    HTML_DOCUMENT,
    MAX_DOCUMENT_BYTES,
    MAX_PDF_PAGES,
    MAX_SHEET_ROWS,
    PDF_DOCUMENT,
    WORD_DOCUMENT,
    ExtractedDocument,
    ExtractedSection,
    skipped,
)

logger = logging.getLogger(__name__)

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

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
        body = ET.fromstring(body_xml).find(f"{_W}body")
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
                root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared = [
                    "".join(t.text or "" for t in si.iter(f"{_S}t")) for si in root.iter(f"{_S}si")
                ]

            sheet_names: list[str] = []
            if "xl/workbook.xml" in names:
                wb = ET.fromstring(archive.read("xl/workbook.xml"))
                sheet_names = [s.get("name") or "" for s in wb.iter(f"{_S}sheet")]

            parts = sorted(n for n in names if n.startswith("xl/worksheets/sheet"))
            sections: list[ExtractedSection] = []
            truncated = False

            for index, part in enumerate(parts):
                sheet = sheet_names[index] if index < len(sheet_names) else f"Sheet{index + 1}"
                root = ET.fromstring(archive.read(part))
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

                header, *body = table
                # One section per block of rows, header repeated — see the note on
                # _SHEET_ROWS_PER_SECTION.
                for start in range(0, max(len(body), 1), _SHEET_ROWS_PER_SECTION):
                    block = body[start : start + _SHEET_ROWS_PER_SECTION]
                    if not block:
                        break
                    lines = _markdown_table([header, *block])
                    first = start + 2  # 1-based, row 1 is the header
                    last = start + 1 + len(block)
                    sections.append(
                        ExtractedSection(f'sheet "{sheet}" rows {first}-{last}', "\n".join(lines))
                    )

        if not sections:
            return skipped("The workbook contains no extractable rows.")
        if truncated:
            logger.info("xlsx truncated at %d rows path=%s", MAX_SHEET_ROWS, path.name)
        return ExtractedDocument(sections=sections)

    # ------------------------------------------------------------------ .html
    def _html(self, path: Path) -> ExtractedDocument:
        parser = _HtmlSections()
        parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
        parser.flush()
        if not parser.sections:
            return skipped("The page contains no extractable text.")
        return ExtractedDocument(sections=parser.sections)

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
            except Exception:  # noqa: BLE001 - a bad page shouldn't lose the good ones
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
