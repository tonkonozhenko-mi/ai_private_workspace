import re

from app.core.domain.handbook_source import display_source_path
from app.core.domain.rag import RagQualityWarning, RagSource

NO_CONTEXT_PHRASES = (
    "no context",
    "no indexed context",
    "context was not found",
)
ABSENCE_PHRASES = (
    "no direct mention",
    "not mentioned",
    "does not contain",
    "not found",
    "absent",
)


def evaluate_rag_answer(
    question: str,
    answer: str,
    sources: list[RagSource],
    source_contents: list[str],
) -> list[RagQualityWarning]:
    if not sources:
        return []

    warnings: list[RagQualityWarning] = []
    normalized_answer = answer.casefold()

    if not answer.strip():
        warnings.append(
            RagQualityWarning(
                code="empty_answer_with_sources",
                message="The answer is empty even though retrieved sources were available.",
                severity="high",
                evidence=[source.source_path for source in sources[:5]],
            )
        )

    matched_no_context_phrases = [
        phrase for phrase in NO_CONTEXT_PHRASES if phrase in normalized_answer
    ]
    if matched_no_context_phrases:
        warnings.append(
            RagQualityWarning(
                code="answer_claims_no_context_despite_sources",
                message="The answer claims context is unavailable despite retrieved sources.",
                severity="high",
                evidence=matched_no_context_phrases,
            )
        )

    # Accept either the raw source path or its human-facing label (the handbook is
    # shown to the model as "Project handbook", so that's what it cites).
    def _mentions(source: RagSource) -> bool:
        return (
            source.source_path.casefold() in normalized_answer
            or display_source_path(source.source_path).casefold() in normalized_answer
        )

    if not any(_mentions(source) for source in sources):
        warnings.append(
            RagQualityWarning(
                code="answer_missing_source_paths",
                message="The answer does not mention any retrieved source path.",
                severity="medium",
                evidence=[source.source_path for source in sources[:5]],
            )
        )

    unsupported = find_unsupported_citations(answer, [source.source_path for source in sources])
    if unsupported:
        warnings.append(
            RagQualityWarning(
                code="answer_cited_unknown_source",
                message=(
                    "The answer referenced files that were not in the retrieved "
                    "context — verify these before trusting them."
                ),
                severity="review",
                evidence=unsupported,
            )
        )

    # Groundedness check: concrete project-specific terms the answer states as
    # fact (backticked identifiers/values: env names, config keys, services) that
    # do not appear anywhere in the retrieved file text. These are the small-model
    # fabrications the citation check above (paths only) misses.
    ungrounded = find_ungrounded_terms(answer, source_contents, already_flagged=unsupported)
    if ungrounded:
        warnings.append(
            RagQualityWarning(
                code="answer_term_not_in_context",
                message=(
                    "The answer states these project-specific terms as fact, but "
                    "they do not appear in the retrieved files — verify them."
                ),
                severity="review",
                evidence=ungrounded,
            )
        )

    # Quote verification: text the answer presents as a verbatim quote (double-
    # quoted spans or code, over ~20 chars) that doesn't appear in any retrieved
    # file. A paraphrase-in-quotes or an invented snippet is a subtle fabrication
    # the term/citation checks above don't catch (they look at identifiers/paths).
    missing_quotes = find_quotes_not_in_sources(answer, source_contents, question=question)
    if missing_quotes:
        warnings.append(
            RagQualityWarning(
                code="quote_not_in_sources",
                message=(
                    "The answer presents quoted text that does not appear verbatim "
                    "in the retrieved files — verify it wasn't paraphrased or invented."
                ),
                severity="review",
                evidence=missing_quotes,
            )
        )

    matched_absence_phrases = [phrase for phrase in ABSENCE_PHRASES if phrase in normalized_answer]
    conflicting_keywords = _find_conflicting_question_keywords(
        question=question,
        source_contents=source_contents,
    )
    if matched_absence_phrases and conflicting_keywords:
        warnings.append(
            RagQualityWarning(
                code="possible_absence_claim_conflict",
                message=(
                    "The answer makes an absence claim, but relevant question "
                    "keywords appear in retrieved context."
                ),
                severity="low",
                evidence=[
                    f"Retrieved context contains question keyword: {keyword}"
                    for keyword in conflicting_keywords[:5]
                ],
            )
        )

    return warnings


# A backtick-quoted token, the form the prompt asks the model to cite source
# paths in (e.g. `main.tf`, `infra/prod/backend.tf`).
_BACKTICK_TOKEN_RE = re.compile(r"`([^`\n]+)`")
# Looks like a file reference: has a path separator or a short file extension.
_FILE_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def find_unsupported_citations(answer: str, source_paths: list[str]) -> list[str]:
    """File-like references the answer cites that are NOT among the retrieved
    source paths — i.e. likely hallucinated citations.

    Only backtick-quoted tokens that look like files (a path separator or a file
    extension) are considered, so prose and bare identifiers don't trip it. Both
    the full path and its basename count as a match, so citing `backend.tf` for
    `infra/backend.tf` is fine. Read-only: it flags, it never edits the answer.
    """
    if not answer or not source_paths:
        return []
    valid: set[str] = set()
    for path in source_paths:
        clean = path.strip()
        if clean:
            valid.add(clean)
            valid.add(clean.split("/")[-1])
    unsupported: list[str] = []
    for raw in _BACKTICK_TOKEN_RE.findall(answer):
        token = raw.strip()
        if not token or token in valid:
            continue
        looks_like_file = "/" in token or bool(_FILE_EXT_RE.search(token))
        if not looks_like_file:
            continue
        if token.split("/")[-1] in valid:
            continue
        unsupported.append(token)
    # De-duplicate, keep order, cap.
    return list(dict.fromkeys(unsupported))[:8]


# A backticked token is "concrete" (a project identifier/value worth grounding,
# not backticked prose) if it carries a separator, a camelCase boundary, is all
# upper-case (an env/const), or contains a digit.
_CAMEL_RE = re.compile(r"[a-z][A-Z]")
_CONCRETE_SEP_RE = re.compile(r"[_./:\-]")


def find_ungrounded_terms(
    answer: str,
    source_contents: list[str],
    already_flagged: list[str] = (),
) -> list[str]:
    """Backticked, concrete project-specific terms the answer asserts as fact that
    appear nowhere in the retrieved file text — likely fabrications.

    Complements :func:`find_unsupported_citations` (which checks file *paths*
    against the retrieved source list): this checks *identifiers and values*
    (env names, config keys, service names) against the retrieved *content*.
    Backticked prose, short words and terms already flagged as bad citations are
    skipped to keep false positives low. Read-only — it flags, never edits.
    """
    if not answer or not source_contents:
        return []
    blob = "\n".join(source_contents).casefold()
    already = set(already_flagged)
    out: list[str] = []
    for raw in _BACKTICK_TOKEN_RE.findall(answer):
        token = raw.strip()
        if not token or token in already or " " in token or len(token) < 3:
            continue
        concrete = (
            bool(_CONCRETE_SEP_RE.search(token))
            or bool(_CAMEL_RE.search(token))
            or token.isupper()
            or any(c.isdigit() for c in token)
        )
        if not concrete:
            continue
        folded = token.casefold()
        if folded in blob or folded.split("/")[-1] in blob:
            continue
        out.append(token)
    return list(dict.fromkeys(out))[:8]


# Verbatim-quote detection. Fenced code blocks (with their optional language tag),
# double-quoted spans (straight or curly), and long inline-code spans are the forms
# a model uses to present text "as quoted from the file".
_FENCED_CODE_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
_DOUBLE_QUOTED_RE = re.compile(r"[\"“]([^\"“”\n]+)[\"”]")
_WHITESPACE_RE = re.compile(r"\s+")
# A quote shorter than this is too small to trust as "verbatim" (and risks
# matching common phrases by chance), so we don't verify it.
_MIN_QUOTE_CHARS = 20
# Fenced-block languages that mark a *runnable command example*, not a quote from a
# file. On a how-to question the model legitimately generates these ("run `terraform
# init && terraform apply`"), so verifying them against the sources is a false
# positive.
_SHELL_LANGS = frozenset(
    {
        "bash",
        "sh",
        "shell",
        "zsh",
        "console",
        "shell-session",
        "shellsession",
        "powershell",
        "ps",
        "ps1",
        "bat",
        "cmd",
    }
)
# The question asks "how do I run/do X" — where generated command examples are
# expected and shouldn't be treated as quotes from the project.
_HOWTO_RE = re.compile(
    r"\bhow\s+(?:do|to|can|would|should|does|might)\b"
    r"|\b(?:command|steps?|instructions?)\s+(?:to|for)\b"
    r"|\brun\b",
    re.IGNORECASE,
)


def _normalize_for_quote(text: str) -> str:
    """Collapse all whitespace and lowercase, so a quote still matches its source
    when the model reflowed indentation or line breaks."""
    return _WHITESPACE_RE.sub(" ", text).strip().casefold()


def _looks_like_howto(question: str) -> bool:
    return bool(_HOWTO_RE.search(question or ""))


def find_quotes_not_in_sources(
    answer: str,
    source_contents: list[str],
    question: str = "",
) -> list[str]:
    """Verbatim quotes (code blocks, double-quoted or long inline-code spans over
    ~20 chars) that don't appear in any retrieved file, whitespace-normalized.

    A quote is a claim of exactness; if it isn't actually in the sources it's a
    paraphrase dressed as a quote, or invented. Read-only — flags, never edits.
    On a how-to question, fenced *shell/command* blocks are skipped: they're
    generated command examples, not quotes from the project's files.
    """
    if not answer or not source_contents:
        return []
    source_blob = _normalize_for_quote("\n".join(source_contents))
    if not source_blob:
        return []

    howto = _looks_like_howto(question)
    candidates: list[str] = []
    for lang, body in _FENCED_CODE_RE.findall(answer):
        if howto and lang.strip().casefold() in _SHELL_LANGS:
            continue  # a generated command example, not a quote from the files
        candidates.append(body)
    candidates.extend(_DOUBLE_QUOTED_RE.findall(answer))
    candidates.extend(
        token
        for token in _BACKTICK_TOKEN_RE.findall(answer)
        if len(token.strip()) > _MIN_QUOTE_CHARS
    )

    missing: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        quote = raw.strip()
        normalized = _normalize_for_quote(quote)
        if len(normalized) <= _MIN_QUOTE_CHARS or normalized in seen:
            continue
        seen.add(normalized)
        if normalized not in source_blob:
            # Trim over-long evidence so the warning stays readable.
            missing.append(quote if len(quote) <= 120 else quote[:117] + "…")
    return missing[:5]


def _find_conflicting_question_keywords(
    question: str,
    source_contents: list[str],
) -> list[str]:
    keywords = {word.casefold() for word in re.findall(r"[A-Za-z0-9_]+", question) if len(word) > 4}
    combined_source_contents = "\n".join(source_contents).casefold()
    return sorted(keyword for keyword in keywords if keyword in combined_source_contents)
