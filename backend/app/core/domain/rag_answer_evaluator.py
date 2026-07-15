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


_THINK_CLOSE = "</think>"


def visible_answer_text(answer: str) -> str:
    """What the person actually reads. A thinking model sometimes emits its
    deliberation inline, closing with ``</think>`` before the real answer; the
    deliberation is a draft, and judging it judged text the user never sees —
    the draft echoes the prompt's own citation example, quotes chunks loosely,
    and lists paths mid-thought, all of which lit up the grounding checks
    (observed 2026-07-15: three of three flagged wiki answers had a clean final
    answer under a noisy draft). Falls back to the full text when stripping
    would leave nothing to judge."""
    if _THINK_CLOSE in answer:
        tail = answer.rsplit(_THINK_CLOSE, 1)[1].strip()
        if tail:
            return tail
    return answer


def evaluate_rag_answer(
    question: str,
    answer: str,
    sources: list[RagSource],
    source_contents: list[str],
) -> list[RagQualityWarning]:
    if not sources:
        return []

    answer = visible_answer_text(answer)
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

    unsupported = find_unsupported_citations(
        answer, [source.source_path for source in sources], source_contents
    )
    if unsupported:
        warnings.append(
            RagQualityWarning(
                code="answer_cited_unknown_source",
                message=(
                    "The answer named files that appear nowhere in the retrieved "
                    "context — they may not exist."
                ),
                severity="high",
                evidence=unsupported,
            )
        )

    # Groundedness check: concrete project-specific terms the answer states as
    # fact (backticked identifiers/values: env names, config keys, services) that
    # do not appear anywhere in the retrieved file text. These are the small-model
    # fabrications the citation check above (paths only) misses.
    ungrounded = find_ungrounded_terms(
        answer,
        source_contents,
        already_flagged=unsupported,
        source_paths=[source.source_path for source in sources],
    )
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


# The citation-format example the prompt shows the model. It must be an obvious
# placeholder, not a plausible filename: the prompt used to demonstrate with
# `main.tf`, small models echoed the example into their answers — and one invented
# "main.tf in the Terraform directory" for a project with no Terraform at all,
# seeded by our own instruction (group run, 2026-07-15). The evaluator ignores
# exactly this token; rag_prompt builds the instruction from it so the two can
# never drift apart.
CITATION_EXAMPLE_PATH = "path/to/file.py"

# A backtick-quoted token, the form the prompt asks the model to cite source
# paths in (e.g. `app/main.py`, `infra/prod/backend.tf`).
_BACKTICK_TOKEN_RE = re.compile(r"`([^`\n]+)`")
# Looks like a file reference: has a path separator or a short file extension.
_FILE_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,6}$")
# The same claim, made in prose: "configuration is in the main.tf file in the
# Terraform directory". Backticks are what the prompt ASKS for, not what a model
# does when it is inventing — the answer that named a Terraform file in a project
# with no Terraform in it wrote the name plainly, and sailed past a check that
# only reads between backticks (mixed-group run, 2026-07-15). The extensions are
# an explicit list rather than "any dot-something", so ordinary prose ("version
# 2.0", "e.g.") is not mistaken for a filename.
#
# Square brackets are part of the name in wiki exports ("[ADR-02]_Invoice
# numbering.md" is a real Confluence-style filename). The first version of this
# pattern excluded them, so it TRUNCATED such names to "_Invoice_numbering.md" —
# a token that matches neither the source path nor the page text — and every
# correct wiki answer that cited its own page in prose was flagged as inventing
# a file (observed 2026-07-15: wiki-export halluc 9.1% → 54.5% overnight, six
# honest answers flagged). A detector with false positives is not stricter, it
# is noisier.
_PROSE_FILE_RE = re.compile(
    r"(?<![\w.\[/-])([\w\[][\w.\[\]/-]*\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|cs|c|cpp|h|"
    r"tf|tfvars|hcl|ya?ml|json|toml|ini|cfg|conf|sh|bash|sql|md|rst|txt|"
    r"proto|gradle|lock|env|dockerfile|tfstate))\b",
    re.IGNORECASE,
)


def _cited_file_tokens(answer: str) -> list[str]:
    """Every file-looking name the answer commits to, backticked or plain.

    A filename claim has a shape: no spaces, and either a basename with an
    extension or a multi-segment path (`k8s/overlays/prod` claims a place exists
    just as `main.tf` does). Models put whole sentences and TRAILING-slash
    directory mentions in backticks too — "`Row-level isolation …
    (wiki/[ADR-04]_Tenant_isolation.md)`", "`wiki/`" (both observed 2026-07-15) —
    and neither is a claim about a specific file, so neither belongs to this
    check. The quote and term checks read those.
    """
    tokens: list[str] = []
    for raw in _BACKTICK_TOKEN_RE.findall(answer):
        token = raw.strip()
        # `(wiki/[Onboarding]_Start_here.md)` — the model wraps the citation-style
        # parentheses INSIDE the backticks (observed 2026-07-15); the parens are
        # punctuation around the name, not part of it. Square brackets stay: they
        # are literally part of wiki filenames.
        while len(token) > 2 and token.startswith("(") and token.endswith(")"):
            token = token[1:-1].strip()
        token = token.rstrip(".,;:")
        if not token or " " in token or token.endswith("/"):
            continue
        if _FILE_EXT_RE.search(token.split("/")[-1]) or "/" in token:
            tokens.append(token)
    tokens.extend(match.strip() for match in _PROSE_FILE_RE.findall(answer))
    return tokens


def find_unsupported_citations(
    answer: str,
    source_paths: list[str],
    source_contents: list[str] | None = None,
) -> list[str]:
    """File-like references the answer names that appear NOWHERE in the evidence —
    neither as a retrieved path nor inside any retrieved file.

    Naming a file is a claim, and this is the cheapest way to check one. Both the
    full path and its basename count as a match, so citing `backend.tf` for
    `infra/backend.tf` is fine, and a file merely *mentioned* by a retrieved
    document counts too — the model read it somewhere, which is the opposite of
    inventing it. What is left is a name the model produced from nothing.

    Read-only: it flags, it never edits the answer.
    """
    if not answer or not source_paths:
        return []
    valid: set[str] = set()
    for path in source_paths:
        clean = path.strip()
        if clean:
            valid.add(clean)
            valid.add(clean.split("/")[-1])
    evidence = "\n".join(source_contents or []).casefold()
    valid_folded = {v.casefold() for v in valid}
    unsupported: list[str] = []
    for token in _cited_file_tokens(answer):
        if token == CITATION_EXAMPLE_PATH:
            continue  # the prompt's own format example, echoed — read, not invented
        if token in valid or token.split("/")[-1] in valid:
            continue
        # A file the retrieved documents talk about was read, not invented. The
        # basename counts here too: a wiki page links "([ADR-01]_Service_split.md)"
        # and the model reasonably writes it back as "wiki/[ADR-01]_Service_split.md"
        # — same file, fuller address (observed 2026-07-15).
        folded_base = token.split("/")[-1].casefold()
        if evidence and (token.casefold() in evidence or folded_base in evidence):
            continue
        # A name broken at a space — "[ADR-01] Service split.md" — leaves a tail
        # like "split.md". If a retrieved path ends with the tail, the model was
        # reaching for that file, clumsily; a fabricated name has no such anchor.
        folded = token.casefold()
        if len(folded) >= 6 and any(v.endswith(folded) for v in valid_folded):
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
    source_paths: list[str] = (),
) -> list[str]:
    """Backticked, concrete project-specific terms the answer asserts as fact that
    appear nowhere in the retrieved file text — likely fabrications.

    Complements :func:`find_unsupported_citations` (which checks file *paths*
    against the retrieved source list): this checks *identifiers and values*
    (env names, config keys, service names) against the retrieved *content*.
    Backticked prose, short words and terms already flagged as bad citations are
    skipped to keep false positives low. So are the retrieved source paths
    themselves and the prompt's citation placeholder: citing `wiki/[Onboarding]_
    Start_here.md` is exactly what the prompt asks for, and a page does not
    contain its own filename — flagging the citation as an ungrounded "term"
    punished obedience (observed 2026-07-15). Read-only — it flags, never edits.
    """
    if not answer or not source_contents:
        return []
    blob = "\n".join(source_contents).casefold()
    already = set(already_flagged)
    grounded_paths: set[str] = {CITATION_EXAMPLE_PATH.casefold()}
    for path in source_paths:
        clean = path.strip().casefold()
        if clean:
            grounded_paths.add(clean)
            grounded_paths.add(clean.split("/")[-1])
    out: list[str] = []
    for raw in _BACKTICK_TOKEN_RE.findall(answer):
        token = raw.strip()
        if not token or token in already or " " in token or len(token) < 3:
            continue
        if token.casefold() in grounded_paths:
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
