"""A document and the folder of assets that belongs to it.

Documentation is never one file. Whatever produced it — a browser saving a
Confluence page, Word's "Save as Web Page", Notion's export, Typora, Obsidian —
the result is the same shape: a document, and beside it a folder named after that
document holding its diagrams, screenshots and spreadsheets.

    [ADR-08]._Invoice_numbering.html
    [ADR-08]._Invoice_numbering_files/
        billing flow.drawio
        billing flow.drawio.png
        style.css                       ← the saver's own chrome, not content

Read without that knowledge, the folder is a heap: a diagram is cited as
"[ADR-08]._Invoice_numbering_files/billing flow.drawio" — which never tells the
reader *which document* it illustrates — and the stylesheet the browser dropped in
is indexed as though it were documentation.

The rule here is deliberately about the *shape*, not about any one tool: a file
inside a folder whose name is a sibling document's name plus a known suffix is an
attachment of that document. It is pure path arithmetic — no file is opened, so it
costs nothing to run over every file in a scan — and when the folder is not that
shape it says so by returning None, leaving ordinary projects untouched.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# The suffixes tools append to a document's name when they save its assets beside
# it. Order matters only for readability; every one is matched.
#   "_files"   Chrome, Firefox, Safari, Word "Save as Web Page", Confluence pages
#              saved from the browser
#   ".assets"  Typora, and Markdown editors that copied it
#   "_media"   Pandoc, some wiki exporters
#   ".files"   older IE/Office layouts
_ASSET_FOLDER_SUFFIXES = ("_files", ".assets", "_media", ".files")

# Extensions a document can have. The companion folder is named after the document
# including or excluding its extension, depending on the tool, so both are tried.
_DOCUMENT_SUFFIXES = (".html", ".htm", ".md", ".docx", ".doc", ".pdf", ".txt", ".rst")

# What the *saver* put there, as opposed to what the author attached. Stylesheets,
# scripts and fonts are how the page looked, never what it said. Only ever skipped
# inside a companion folder: a .css a person keeps in their own project is theirs.
_CHROME_SUFFIXES = frozenset(
    {".css", ".js", ".mjs", ".map", ".ico", ".woff", ".woff2", ".ttf", ".eot"}
)


def _strip_asset_suffix(folder_name: str) -> str | None:
    """ "Page_files" → "Page"; None when the folder is not a companion folder."""
    for suffix in _ASSET_FOLDER_SUFFIXES:
        if folder_name.endswith(suffix) and len(folder_name) > len(suffix):
            return folder_name[: -len(suffix)]
    return None


def document_title(document_path: str) -> str:
    """A human title for a document, from its file name.

    "[CAT-1]_Ref_Price_Data.html" → "[CAT-1] Ref Price Data". Savers replace
    spaces (and often punctuation) with underscores, so undoing that is the closest
    we get to the real title without opening the file — and when we do open it, the
    document's own title wins.
    """
    name = PurePosixPath(document_path).name
    for suffix in _DOCUMENT_SUFFIXES:
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return " ".join(name.replace("._", " ").replace("_", " ").split())


def owning_document(relative_path: str, known_paths: set[str] | None = None) -> str | None:
    """The document an attachment belongs to, or None if this is not an attachment.

    "notes/Design_files/diagram.drawio" → "notes/Design.html" when that file exists.
    ``known_paths`` is the set of files the scan actually found; without it we cannot
    tell which extension the document has, so the *stem* is returned and the caller
    treats it as a title. Passing the real file list is what turns a guess into a
    fact — and if no sibling document exists, this was never a companion folder and
    the answer is None.
    """
    parts = PurePosixPath(relative_path).parts
    for index, part in enumerate(parts[:-1]):
        stem = _strip_asset_suffix(part)
        if stem is None:
            continue
        parent = PurePosixPath(*parts[:index]) if index else None
        if known_paths is None:
            return str(parent / stem) if parent else stem
        for suffix in _DOCUMENT_SUFFIXES:
            candidate = f"{stem}{suffix}"
            full = str(parent / candidate) if parent else candidate
            if full in known_paths:
                return full
        return None
    return None


def is_saver_chrome(relative_path: str) -> bool:
    """Stylesheets, scripts and fonts a saver dropped into a companion folder."""
    if owning_document(relative_path) is None:
        return False
    return PurePosixPath(relative_path).suffix.lower() in _CHROME_SUFFIXES


def origin_note(relative_path: str, known_paths: set[str] | None = None) -> str | None:
    """One line of provenance for the chunk header, or None when there is nothing to say.

    An attachment is announced by the document it belongs to — "attachment of
    'Invoice numbering'" — because that, not the folder name, is what a person
    searches for and what makes the citation checkable.
    """
    owner = owning_document(relative_path, known_paths)
    if owner is None:
        return None
    return f'attachment of "{document_title(owner)}"'
