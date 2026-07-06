"""Deterministic domain-synonym expansion for the retrieval query.

A user asks in one vocabulary ("Content-Security-Policy") while the file uses
another ("csp"); dense + BM25 both miss the lexical gap. This appends the known
alternate forms of any recognised term to the search query, so retrieval lands
whichever spelling the codebase happens to use. Pure and deterministic — a fixed
table, no model, ~0 latency — so it's always on (unlike the optional LLM rewrite).

Only *adds* tokens to the query; it never removes or reorders the user's wording,
so it can't make retrieval worse than the no-expansion baseline. Groups are
symmetric: any member present pulls in the others.
"""

from __future__ import annotations

import re

# Each tuple is a set of interchangeable terms; when any appears in the query, the
# missing members are appended. Kept to infra/dev vocabulary where the abbreviation
# vs. full-form gap is common and unambiguous.
_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("content-security-policy", "content security policy", "csp"),
    ("kubernetes", "k8s"),
    ("development", "dev"),
    ("production", "prod"),
    ("staging", "stage"),
    ("environment", "env"),
    ("configuration", "config"),
    ("repository", "repo"),
    ("database", "db"),
    ("authentication", "auth"),
    ("authorization", "authz"),
    ("infrastructure", "infra"),
    ("continuous integration", "ci"),
    ("continuous deployment", "cd"),
    ("ci/cd", "cicd", "ci cd"),
    ("docker compose", "docker-compose"),
    ("terraform", "tf"),
    ("github actions", "gh actions"),
    ("gitlab ci", "gitlab-ci"),
    ("javascript", "js"),
    ("typescript", "ts"),
    ("application", "app"),
    ("dependencies", "deps"),
    ("documentation", "docs"),
    ("relevance", "relevancy"),
    ("embedding", "embeddings"),
)


def _member_pattern(term: str) -> re.Pattern[str]:
    # Match the term as a whole token. Word boundaries handle hyphens/slashes
    # (non-word chars) at the edges; internal spaces/hyphens are matched literally.
    return re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)


_COMPILED: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (_member_pattern(term), term) for group in _SYNONYM_GROUPS for term in group
)
# term -> its group, for quick lookup of what to add.
_GROUP_OF: dict[str, tuple[str, ...]] = {
    term: group for group in _SYNONYM_GROUPS for term in group
}


def synonym_additions(query: str) -> list[str]:
    """The alternate forms to add for a query — the members of every matched group
    that aren't already present. Deterministic order (group order, then member
    order), de-duplicated."""
    if not query:
        return []
    present_terms = [term for pattern, term in _COMPILED if pattern.search(query)]
    if not present_terms:
        return []
    present_set = {t.lower() for t in present_terms}
    additions: list[str] = []
    seen: set[str] = set()
    for group in _SYNONYM_GROUPS:
        if not any(member.lower() in present_set for member in group):
            continue
        for member in group:
            low = member.lower()
            if low in present_set or low in seen:
                continue
            # Skip a form already literally in the query (e.g. matched by another
            # group member's substring) to avoid redundant tokens.
            if _member_pattern(member).search(query):
                continue
            additions.append(member)
            seen.add(low)
    return additions


def expand_query_synonyms(query: str) -> str:
    """Return the query with domain-synonym alternates appended. Unchanged when
    nothing matches."""
    additions = synonym_additions(query)
    if not additions:
        return query
    return f"{query} {' '.join(additions)}"
