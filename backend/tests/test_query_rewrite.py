from app.core.domain.rag_query_rewrite import (
    build_query_rewrite_prompt,
    merge_queries,
    parse_rewritten_query,
)


def test_prompt_contains_question_and_no_context_by_default():
    prompt = build_query_rewrite_prompt("How do I disable the cache?")
    assert "How do I disable the cache?" in prompt
    assert "Recent conversation" not in prompt
    assert prompt.rstrip().endswith("Search query:")


def test_prompt_includes_prior_terms_when_given():
    prompt = build_query_rewrite_prompt("disable it", prior_terms="redis cache layer")
    assert "Recent conversation" in prompt
    assert "redis cache layer" in prompt


def test_parse_strips_prefix_and_quotes():
    assert parse_rewritten_query('Search query: "redis cache ttl"', "orig") == "redis cache ttl"


def test_parse_falls_back_on_empty():
    assert parse_rewritten_query("   ", "original question") == "original question"


def test_parse_falls_back_on_overlong_reply():
    rambling = "Sure! " + "word " * 100
    assert parse_rewritten_query(rambling, "orig") == "orig"


def test_parse_keeps_only_first_line():
    assert parse_rewritten_query("redis cache ttl\nexplanation here", "orig") == "redis cache ttl"


def test_merge_appends_new_terms():
    merged = merge_queries("how do I disable it", "redis cache ttl disable")
    assert "how do I disable it" in merged
    assert "redis cache ttl disable" in merged


def test_merge_skips_when_rewrite_contained():
    # Rewrite adds nothing new -> keep original single copy.
    assert merge_queries("redis cache ttl", "Redis Cache") == "redis cache ttl"
