"""Reading a file someone drops into the chat.

The project index has read Word, Excel, PDF and slides for a long time — through
a DocumentTextExtractor, because those are binary or markup containers and
reading them as UTF-8 yields garbage. Attaching a file to a question did not use
any of that: the browser read it as text and sent whatever came out. Attach a
Word document and the model receives mojibake with a filename on top, so it
answers from the filename — which is exactly what it looks like from outside:
the app "read" the document and then could not say anything about its contents.

The two judgements that are not the extractor's live here, where they can be
tested without a filesystem.
"""

# Formats we cannot read at all, named so the refusal can say something useful.
# These are not "unsupported file types" in the abstract — they are the formats
# a person actually has lying around, and each one has a way out that takes ten
# seconds in the app that produced it.
LEGACY_OFFICE_FORMATS: dict[str, tuple[str, str]] = {
    ".doc": ("Word 97–2003", "Word: File → Save As → .docx"),
    ".xls": ("Excel 97–2003", "Excel: File → Save As → .xlsx"),
    ".ppt": ("PowerPoint 97–2003", "PowerPoint: File → Save As → .pptx"),
    ".rtf": ("Rich Text Format", "Word: File → Save As → .docx"),
    ".pages": ("Apple Pages", "Pages: File → Export To → Word"),
    ".numbers": ("Apple Numbers", "Numbers: File → Export To → Excel"),
    ".key": ("Apple Keynote", "Keynote: File → Export To → PowerPoint"),
    ".odt": ("OpenDocument Text", "Save as .docx"),
    ".ods": ("OpenDocument Spreadsheet", "Save as .xlsx"),
    ".odp": ("OpenDocument Presentation", "Save as .pptx"),
}


def legacy_format_refusal(filename: str) -> str | None:
    """Why this file cannot be read, and what to do about it — or None.

    Saying "unsupported file" would be true and useless. A person who attached a
    .doc wants to know that the app reads the newer format and that their own
    Word converts it, not that a category of thing was rejected.
    """
    suffix = _suffix(filename)
    known = LEGACY_OFFICE_FORMATS.get(suffix)
    if known is None:
        return None
    name, how = known
    return f"{name} files ({suffix}) cannot be read. Save it as the newer format first — {how}."


def looks_like_text(sample: bytes) -> bool:
    """Whether these bytes are plausibly something a person wrote.

    The last line of defence, for a binary format nobody thought to name. Sending
    its bytes to the model as if they were words wastes the context window and
    produces an answer built on noise — worse than saying we could not read it,
    because it looks like an answer.

    NUL bytes settle it: text files do not contain them, and every binary
    container tested does within the first few kilobytes.
    """
    if not sample:
        return True  # An empty file is empty, not binary.
    if b"\x00" in sample:
        return False
    # Undecodable bytes are the other tell. UTF-8 is the only encoding we claim
    # to read; a file that is not valid UTF-8 and not valid Latin-1 text is not
    # something we should be guessing at.
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    # Control characters that are not whitespace. Deliberately lenient: a log
    # coloured with ANSI escapes is full of them and is exactly the kind of file
    # people attach. Anything genuinely binary has almost always been caught by
    # the two checks above — this only has to notice a blob that happens to
    # contain no NUL and happens to decode.
    control = sum(1 for ch in text if ord(ch) < 32 and ch not in "\t\n\r\f\v")
    return control <= max(16, len(text) // 20)


def _suffix(filename: str) -> str:
    name = (filename or "").strip().lower()
    dot = name.rfind(".")
    return name[dot:] if dot > 0 else ""
