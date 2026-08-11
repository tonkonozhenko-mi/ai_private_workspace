"""The words in an RTF document, without its formatting.

RTF is not a container like .docx or .odt — the text is already there, in plain
ASCII, under a layer of control words. So this is not a parser for a binary
format; it is a small state machine that peels the layer off. Worth the eighty
lines, because the alternative is telling someone their document is unreadable
when it plainly is not.

What it deliberately does not do: fonts, colours, tables-as-tables, embedded
images. Those are how the document *looks*. What reaches the model is what it
says.
"""

import re

# One pass, five alternatives: a control word with optional numeric parameter,
# a \'hh byte escape, a control symbol, a brace, or a run of ordinary text.
_TOKEN = re.compile(
    r"""
    \\([a-zA-Z]+)(-?\d+)?[ ]?   # \par, \u1055, \fs24 — trailing space is a delimiter
    | \\'([0-9a-fA-F]{2})       # \'e9 — a byte in the document's code page
    | \\([^a-zA-Z])             # \\, \{, \}, \~ — an escaped character
    | ([{}])                    # group boundaries
    | ([^\\{}]+)                # everything else is text
    """,
    re.VERBOSE,
)

# Groups whose contents are machinery rather than prose. Skipping them is what
# keeps a font list out of the answer.
_SKIPPED_GROUPS = frozenset(
    {
        "fonttbl",
        "colortbl",
        "stylesheet",
        "info",
        "pict",
        "themedata",
        "colorschememapping",
        "latentstyles",
        "datastore",
        "generator",
    }
)

_BREAKS = frozenset({"par", "line", "sect", "page"})
_TABS = frozenset({"tab", "cell"})


def rtf_to_text(rtf: str) -> str:
    """Plain text from RTF source. Never raises: a malformed document yields
    whatever text could be recovered, which may be nothing."""
    out: list[str] = []
    depth = 0
    # The depth at which a skipped group started; everything deeper is machinery.
    skipping_from: int | None = None
    # Every \uN is followed by a plain-ASCII stand-in for readers that cannot do
    # Unicode — "К?о?д?" is what you get by taking both. \ucN says how many
    # characters the stand-in occupies; one, unless the document says otherwise.
    fallback_width = 1
    pending_fallback = 0

    for match in _TOKEN.finditer(rtf):
        word, param, hex_escape, symbol, brace, text = match.groups()

        if brace == "{":
            depth += 1
            continue
        if brace == "}":
            depth -= 1
            if skipping_from is not None and depth <= skipping_from:
                skipping_from = None
            continue
        if skipping_from is not None:
            continue

        if word:
            if word in _SKIPPED_GROUPS:
                # The group's own opening brace was counted before this word.
                skipping_from = depth - 1
            elif word in _BREAKS:
                out.append("\n")
            elif word in _TABS:
                out.append("\t")
            elif word == "uc" and param:
                fallback_width = max(0, int(param))
            elif word == "u" and param:
                # \uN is a signed 16-bit code point; negatives have wrapped.
                code = int(param)
                out.append(chr(code if code >= 0 else code + 65536))
                pending_fallback = fallback_width
            continue

        if hex_escape:
            # cp1252 is what Word writes by default. Getting the code page from
            # \ansicpg would be more correct and is a refinement, not a fix:
            # guessing wrong costs an accent, not the sentence.
            out.append(bytes([int(hex_escape, 16)]).decode("cp1252", errors="ignore"))
            continue

        if symbol:
            out.append({"\\": "\\", "{": "{", "}": "}", "~": " ", "_": "-"}.get(symbol, ""))
            continue

        if text:
            if pending_fallback:
                # Drop the stand-in that belongs to the \u just emitted.
                dropped = min(pending_fallback, len(text))
                text = text[dropped:]
                pending_fallback -= dropped
            if text:
                out.append(text)

    joined = "".join(out).replace("\r", "")
    return "\n".join(line.strip() for line in joined.split("\n") if line.strip())
