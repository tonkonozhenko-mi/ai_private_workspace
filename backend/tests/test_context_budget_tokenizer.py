from app.core.domain.context_budget import chunk_char_budget


def test_default_uses_estimate():
    assert chunk_char_budget(8192) > 0


def test_custom_counter_changes_budget():
    # A counter that reports more tokens (1 per char) leaves less room than the
    # default ~4-chars-per-token estimate, so the chunk budget shrinks.
    base = chunk_char_budget(8192, memory_text="x" * 400)
    exact = chunk_char_budget(8192, memory_text="x" * 400, token_counter=lambda t: len(t))
    assert exact < base


def test_counter_is_applied_to_memory_and_history():
    seen = []

    def counter(text: str) -> int:
        seen.append(text)
        return 1

    chunk_char_budget(
        8192,
        memory_text="mem",
        history=[("user", "a"), ("assistant", "b")],
        token_counter=counter,
    )
    assert "mem" in seen and "a" in seen and "b" in seen
