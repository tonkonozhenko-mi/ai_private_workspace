"""Which language the answer is written in, decided in one place.

Maks asked, in Russian, for onboarding documentation "and all of it must be in
English". Mistral answered in Ukrainian. Three languages were pulling at once —
the question's, the instruction's, and the corpus's (a Ukrainian wiki) — and the
prompt said nothing at all about language, so the model picked whichever the
retrieved text was written in.

That is not a model being wilful, it is us never having asked. There is a saved
style preference, but it is a cross-project setting, not a reading of what the
person just said. So the rule is stated, at the end of the prompt where a small
model remembers it best, in the order a person would expect:

1. What they asked for in this very question wins. "In English", "по-русски",
   "answer in Ukrainian" — an explicit instruction is the strongest thing in the
   room, and it must beat a preference set weeks ago.
2. Otherwise, their saved preference (About you), if they set one.
3. Otherwise, the language they wrote the question in. Not the language of the
   documents: a Ukrainian wiki answering a Russian question in Ukrainian is the
   corpus talking over the person.

Detection is deliberately small: an explicit request is a short, recognisable
phrase, and the script a question is written in is countable. Nothing here calls
a model — deciding what language to speak must not itself cost a generation.
"""

from __future__ import annotations

import re

# "in English", "на английском", "англійською", "reply in Ukrainian", …
_LANGUAGE_NAMES: dict[str, tuple[str, ...]] = {
    "English": ("english", "англ", "англий", "англій", "інгліш"),
    "Russian": ("russian", "русск", "росій", "по-русски"),
    "Ukrainian": ("ukrainian", "украин", "українськ", "укр"),
    "German": ("german", "deutsch", "немецк", "німецьк"),
    "French": ("french", "français", "французск"),
    "Spanish": ("spanish", "español", "испанск"),
    "Polish": ("polish", "polski", "польск"),
}

# A language named after a preposition: "in English", "на английском",
# "англійською". This is the part that identifies WHICH language.
_NAMED = re.compile(
    r"\b(?:in|на|по|у|в)[\s-]*(?P<name>[a-zA-Zа-яёіїєґА-ЯЁІЇЄҐ]{3,})"
    r"|(?P<solo>[a-zA-Zа-яёіїєґА-ЯЁІЇЄҐ]{4,}(?:ською|ською\s+мовою|ском|ски))\b",
    re.IGNORECASE,
)

# And the part that makes it an instruction rather than a remark: somewhere in
# the question, a word about writing or answering. "The English docs are
# outdated" names a language and asks for nothing; "write it in English" does.
#
# Matched loosely on purpose — stems, not whole words — because this is typed by
# a person in a hurry on whatever keyboard they have. "всё должно біть на
# английском" is a Ukrainian-layout slip for "быть" and asks exactly as clearly
# as the correctly spelled version; a rule that a typo can switch off is not a
# rule the person can rely on.
_WRITING_INTENT = re.compile(
    r"answer|reply|respond|writ|say it|put it|translat|must be|should be|all in|"
    r"everything in|"
    r"ответ|отвеч|напиш|написа|перевед|должно|должн|"
    r"відповід|напис|переклад|має бути|повинн|усе|все",
    re.IGNORECASE,
)


def requested_language(question: str) -> str | None:
    """The language this question explicitly asks the answer to be in, or None.

    Two things must be present: a language named after a preposition, and a word
    about writing or answering somewhere in the question. A mention on its own
    ("the English docs are outdated") asks for nothing and must not override a
    preference the person set deliberately.
    """
    text = question or ""
    if not _WRITING_INTENT.search(text):
        return None
    for match in _NAMED.finditer(text):
        candidate = (match.group("name") or match.group("solo") or "").lower()
        for language, stems in _LANGUAGE_NAMES.items():
            if any(candidate.startswith(stem) for stem in stems):
                return language
    return None


def question_script_language(question: str) -> str | None:
    """The language the question itself is written in, as far as script tells us.

    Script, not vocabulary: distinguishing Russian from Ukrainian by wording is a
    research problem, but Ukrainian-only letters are a fact. Returns None when
    the question is too short or mixed to say — and None means the prompt names
    no language, which is better than naming the wrong one.
    """
    text = question or ""
    if not text.strip():
        return None
    if re.search(r"[іїєґІЇЄҐ]", text):
        return "Ukrainian"
    cyrillic = len(re.findall(r"[а-яёА-ЯЁ]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    if cyrillic > latin and cyrillic >= 4:
        return "Russian"
    if latin > cyrillic and latin >= 4:
        return "English"
    return None


def answer_language_directive(question: str, saved_preference: str = "") -> str:
    """The line the prompt carries about language, or "" when it has nothing to
    say. Order: what was asked now, then what was saved, then how it was written.
    """
    asked = requested_language(question)
    if asked:
        return (
            f"Write the entire answer in {asked}, because that is what was asked "
            f"for — even if the question or the source documents are in another "
            f"language."
        )
    if saved_preference.strip():
        # The saved preference is free text the person wrote about themselves;
        # it is passed through rather than parsed, since they phrased it.
        return saved_preference.strip()
    written_in = question_script_language(question)
    if written_in:
        return (
            f"Write the answer in {written_in}, the language of the question — "
            f"not the language the source documents happen to be written in."
        )
    return ""
