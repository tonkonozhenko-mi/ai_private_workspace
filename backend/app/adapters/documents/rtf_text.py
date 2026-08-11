"""The words in an RTF document, without its formatting.

RTF is not a container like .docx or .odt — the text is already there, in plain
ASCII, under a layer of control words. So this is not a parser for a binary
format; it is a small reader that peels the layer off. Worth having, because the
alternative is telling someone their document is unreadable when it plainly is
not.

What it deliberately does not do: fonts, colours, tables-as-tables, embedded
images. Those are how the document *looks*. What reaches the model is what it
says.
"""

import re

# One pass, five alternatives: a control word with optional numeric parameter,
# a \'hh byte escape, a control symbol, a brace, or a run of ordinary text.
_TOKEN = re.compile(
    r"""
    \\([a-zA-Z]+)(-?\d+)?[ ]?   # \par, \u1055, \fs24 — a trailing space delimits
    | \\'([0-9a-fA-F]{2})       # \'e9 — a byte in the document's code page
    | \\([^a-zA-Z])             # \\, \{, \}, \~ — an escaped character
    | ([{}])                    # group boundaries
    | ([^\\{}]+)                # everything else is text
    """,
    re.VERBOSE,
)

# Groups whose contents are machinery rather than prose. Skipping them is what
# keeps a list of typefaces out of the answer.
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


class _Reader:
    """One document's worth of reading state.

    A class rather than one long loop because the state is what makes this
    fiddly — three variables that only three of the branches touch — and a
    method per kind of token is easier to be sure about than a ladder inside a
    ladder.
    """

    def __init__(self) -> None:
        self.out: list[str] = []
        self.depth = 0
        # The depth at which a skipped group began; everything deeper is machinery.
        self.skipping_from: int | None = None
        # Every \uN is followed by a plain-ASCII stand-in for readers that cannot
        # do Unicode — "П?р?и?в?і?т?" is what you get by keeping both. \ucN says how
        # many characters the stand-in occupies; one, unless told otherwise.
        self.fallback_width = 1
        self.pending_fallback = 0

    @property
    def skipping(self) -> bool:
        return self.skipping_from is not None

    def brace(self, which: str) -> None:
        if which == "{":
            self.depth += 1
            return
        self.depth -= 1
        if self.skipping_from is not None and self.depth <= self.skipping_from:
            self.skipping_from = None

    def control_word(self, word: str, param: str | None) -> None:
        if word in _SKIPPED_GROUPS:
            # The group's own opening brace was counted before this word.
            self.skipping_from = self.depth - 1
        elif word in _BREAKS:
            self.out.append("\n")
        elif word in _TABS:
            self.out.append("\t")
        elif word == "uc" and param:
            self.fallback_width = max(0, int(param))
        elif word == "u" and param:
            # \uN is a signed 16-bit code point; negatives have wrapped.
            code = int(param)
            self.out.append(chr(code if code >= 0 else code + 65536))
            self.pending_fallback = self.fallback_width

    def hex_byte(self, digits: str) -> None:
        # cp1252 is what Word writes by default. Reading the code page from
        # \ansicpg would be more correct and is a refinement, not a fix: guessing
        # wrong costs an accent, not the sentence.
        self.out.append(bytes([int(digits, 16)]).decode("cp1252", errors="ignore"))

    def symbol(self, char: str) -> None:
        self.out.append({"\\": "\\", "{": "{", "}": "}", "~": " ", "_": "-"}.get(char, ""))

    def text(self, run: str) -> None:
        if self.pending_fallback:
            # Drop the stand-in belonging to the \u just emitted.
            dropped = min(self.pending_fallback, len(run))
            run = run[dropped:]
            self.pending_fallback -= dropped
        if run:
            self.out.append(run)

    def result(self) -> str:
        joined = "".join(self.out).replace("\r", "")
        return "\n".join(line.strip() for line in joined.split("\n") if line.strip())


def rtf_to_text(rtf: str) -> str:
    """Plain text from RTF source. Never raises: a malformed document yields
    whatever text could be recovered, which may be nothing."""
    reader = _Reader()
    for match in _TOKEN.finditer(rtf):
        word, param, hex_escape, symbol, brace, text = match.groups()
        if brace:
            reader.brace(brace)
        elif reader.skipping:
            continue
        elif word:
            reader.control_word(word, param)
        elif hex_escape:
            reader.hex_byte(hex_escape)
        elif symbol:
            reader.symbol(symbol)
        elif text:
            reader.text(text)
    return reader.result()
