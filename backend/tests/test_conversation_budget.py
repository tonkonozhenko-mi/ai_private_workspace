from app.core.domain.conversation_budget import (
    build_summary_prompt,
    estimate_turn_tokens,
    history_token_budget,
    split_history_by_budget,
)


def test_history_budget_scales_with_window_and_has_floor():
    assert history_token_budget(8192) == 1500  # capped
    assert history_token_budget(2048) == 512  # window // 4
    assert history_token_budget(64) >= 256  # floor
    assert history_token_budget(None) == 1500


def test_split_keeps_recent_within_budget():
    turns = [("user", "a" * 400), ("assistant", "b" * 400), ("user", "c" * 400)]
    # budget ~ 100 tokens (400 chars) -> only the last turn fits.
    older, recent = split_history_by_budget(turns, token_budget=100)
    assert [c[1][0] for c in recent] == ["c"]
    assert len(older) == 2
    assert [c[1][0] for c in older] == ["a", "b"]


def test_split_keeps_at_least_last_turn_even_if_oversized():
    turns = [("user", "x" * 10_000)]
    older, recent = split_history_by_budget(turns, token_budget=1)
    assert recent == turns
    assert older == []


def test_split_all_fit_when_budget_ample():
    turns = [("user", "hi"), ("assistant", "hello")]
    older, recent = split_history_by_budget(turns, token_budget=10_000)
    assert older == []
    assert recent == turns
    assert estimate_turn_tokens("hello") == 1


def test_summary_prompt_includes_turns_and_ends_with_marker():
    prompt = build_summary_prompt([("user", "set up ECS in dev"), ("assistant", "done")])
    assert "User: set up ECS in dev" in prompt
    assert "Assistant: done" in prompt
    assert prompt.rstrip().endswith("Summary:")
