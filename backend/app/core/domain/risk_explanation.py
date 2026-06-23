"""Human-readable framing for a project finding.

Turns a deterministic :class:`ProjectFinding` into a calm, review-oriented
explanation: what was found, why it may matter, where, how confident we are, and
what to check manually. The language is deliberately *needs review*, never "this
is broken" — a finding is a lead for a human, not a verdict.

Everything here is derived from the finding's own ``category`` / ``severity`` /
``confidence``. No technology names are hardcoded: the "why it may matter" and
"what to check" text describes the *kind* of issue (security, reliability,
deployment, configuration, testing, observability), which is generic and stable.
No LLM is involved.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.domain.project_graph import Confidence, FindingCategory, ProjectFinding

# Why a finding of each *category* may matter — the generic semantics of that
# kind of issue, independent of any specific tool or technology.
_WHY_BY_CATEGORY: dict[str, str] = {
    FindingCategory.SECURITY: (
        "Touches access, secrets, or exposure. If it is broader than intended, it "
        "can let the wrong people or services reach something they should not."
    ),
    FindingCategory.RELIABILITY: (
        "Affects how dependably the system keeps running. Worth confirming it "
        "behaves under load or partial failure."
    ),
    FindingCategory.DEPLOYMENT: (
        "Shapes how changes ship to an environment. A gap here can let an "
        "unintended change reach production."
    ),
    FindingCategory.CONFIGURATION: (
        "Configuration that drives runtime behaviour. The risk is a value that is "
        "right for one environment but wrong for another."
    ),
    FindingCategory.TESTING: (
        "Relates to how well changes are verified. Thin coverage here means "
        "regressions are easy to miss."
    ),
    FindingCategory.OBSERVABILITY: (
        "Affects how visible the system is in operation. Gaps make incidents "
        "slower to notice and diagnose."
    ),
    FindingCategory.GENERAL: (
        "Flagged for awareness. Review whether it matches what you intended."
    ),
}

# What a human should check, per category — phrased as questions to investigate,
# never as fixes to apply automatically.
_CHECK_BY_CATEGORY: dict[str, list[str]] = {
    FindingCategory.SECURITY: [
        "Is this intentional, and scoped to only the component that needs it?",
        "Are secrets, credentials, or public access involved?",
    ],
    FindingCategory.RELIABILITY: [
        "Is there a retry, timeout, or fallback where this could fail?",
        "What happens to in-flight work if this part goes down?",
    ],
    FindingCategory.DEPLOYMENT: [
        "Which environment does this path actually reach?",
        "Is there an approval or guard before it touches production?",
    ],
    FindingCategory.CONFIGURATION: [
        "Does this value differ correctly across dev / staging / production?",
        "Is any secret stored here in plain text?",
    ],
    FindingCategory.TESTING: [
        "Is the flow this touches covered by a test?",
        "Were recent changes here verified before shipping?",
    ],
    FindingCategory.OBSERVABILITY: [
        "Are there logs, metrics, or alerts for this path?",
    ],
    FindingCategory.GENERAL: [
        "Does this match what you intended for the project?",
    ],
}

# How sure we are the finding is real — turned into plain language.
_CONFIDENCE_LABEL: dict[str, str] = {
    Confidence.HIGH: "Clearly present in the files",
    Confidence.MEDIUM: "Likely, but worth confirming",
    Confidence.LOW: "Possible — inferred, confirm before acting",
}

# Severity, softened into "how much attention", never "how broken".
_ATTENTION_BY_SEVERITY: dict[str, str] = {
    "high": "Worth a close look",
    "medium": "Worth reviewing",
    "low": "Minor — review when convenient",
    "info": "For awareness",
}


@dataclass(frozen=True)
class RiskExplanation:
    """A calm, review-oriented projection of a single finding."""

    what: str  # what was found (the finding's own explanation/title)
    why_it_may_matter: str  # generic, category-derived
    where: str | None  # source file, if known
    confidence_label: str  # plain-language confidence
    attention: str  # softened severity ("Worth a close look")
    review_status: str  # always review-oriented, never a verdict
    check_manually: list[str]  # questions for a human to investigate
    suggested_idea: str | None  # the recommendation, framed as an idea only

    def as_dict(self) -> dict:
        return {
            "what": self.what,
            "why_it_may_matter": self.why_it_may_matter,
            "where": self.where,
            "confidence_label": self.confidence_label,
            "attention": self.attention,
            "review_status": self.review_status,
            "check_manually": list(self.check_manually),
            "suggested_idea": self.suggested_idea,
        }


def explain_finding(finding: ProjectFinding) -> RiskExplanation:
    """Derive a human-readable, review-oriented explanation for a finding.

    Pure and deterministic — same finding in, same explanation out.
    """
    category = finding.category if finding.category in _WHY_BY_CATEGORY else FindingCategory.GENERAL
    what = (finding.explanation or finding.title or "").strip()

    confidence_label = _CONFIDENCE_LABEL.get(
        finding.confidence, "Confidence not stated — confirm before acting"
    )
    attention = _ATTENTION_BY_SEVERITY.get(finding.severity, "Worth reviewing")

    # The review status is always a prompt to look, never a judgement. Lower
    # confidence leans harder on "confirm first".
    if finding.confidence == Confidence.HIGH:
        review_status = "Needs review"
    else:
        review_status = "Needs review — confirm it is real first"

    suggested = (finding.recommendation or "").strip() or None

    return RiskExplanation(
        what=what,
        why_it_may_matter=_WHY_BY_CATEGORY[category],
        where=finding.source_file,
        confidence_label=confidence_label,
        attention=attention,
        review_status=review_status,
        check_manually=list(_CHECK_BY_CATEGORY[category]),
        suggested_idea=suggested,
    )
