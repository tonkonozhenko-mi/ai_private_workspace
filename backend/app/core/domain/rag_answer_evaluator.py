import re

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

    if not any(source.source_path.casefold() in normalized_answer for source in sources):
        warnings.append(
            RagQualityWarning(
                code="answer_missing_source_paths",
                message="The answer does not mention any retrieved source path.",
                severity="medium",
                evidence=[source.source_path for source in sources[:5]],
            )
        )

    unsupported = find_unsupported_citations(
        answer, [source.source_path for source in sources]
    )
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


def _find_conflicting_question_keywords(
    question: str,
    source_contents: list[str],
) -> list[str]:
    keywords = {word.casefold() for word in re.findall(r"[A-Za-z0-9_]+", question) if len(word) > 4}
    combined_source_contents = "\n".join(source_contents).casefold()
    return sorted(keyword for keyword in keywords if keyword in combined_source_contents)
