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

    if not any(
        source.source_path.casefold() in normalized_answer for source in sources
    ):
        warnings.append(
            RagQualityWarning(
                code="answer_missing_source_paths",
                message="The answer does not mention any retrieved source path.",
                severity="medium",
                evidence=[source.source_path for source in sources[:5]],
            )
        )

    matched_absence_phrases = [
        phrase for phrase in ABSENCE_PHRASES if phrase in normalized_answer
    ]
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


def _find_conflicting_question_keywords(
    question: str,
    source_contents: list[str],
) -> list[str]:
    keywords = {
        word.casefold()
        for word in re.findall(r"[A-Za-z0-9_]+", question)
        if len(word) > 4
    }
    combined_source_contents = "\n".join(source_contents).casefold()
    return sorted(
        keyword for keyword in keywords if keyword in combined_source_contents
    )
