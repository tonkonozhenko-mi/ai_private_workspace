"""A chat template that raises costs the whole answer, so we hand it a shape it
accepts — without editing what anyone said.

Live, 16.07: llama-server returned HTTP 400 "Conversation roles must alternate
user/assistant/user/assistant" and the person was told the model could not
answer. The retry worked, so the sequence that caused it was gone before I could
read it; these tests cover the shapes our own code can produce, not a
reconstruction of that particular thread.
"""

from app.core.domain.chat_turns import alternating_turns, turns_before_user_message


def test_an_ordinary_conversation_is_left_alone():
    turns = [("user", "Where are reports stored?"), ("assistant", "Object storage.")]

    assert alternating_turns(turns) == turns


def test_two_user_messages_become_one_that_keeps_both():
    """The summary preface in front of a history that already starts with the
    user. Merging is the point: dropping either would rewrite the question."""
    turns = [("user", "[Summary] We discussed report storage."), ("user", "Where is that set?")]

    merged = alternating_turns(turns)

    assert len(merged) == 1
    assert merged[0][0] == "user"
    assert "[Summary] We discussed report storage." in merged[0][1]
    assert "Where is that set?" in merged[0][1]


def test_two_assistant_messages_are_merged_too():
    turns = [("user", "Q"), ("assistant", "First half."), ("assistant", "Second half.")]

    merged = alternating_turns(turns)

    assert [role for role, _ in merged] == ["user", "assistant"]
    assert merged[1][1] == "First half.\n\nSecond half."


def test_a_history_that_opens_with_the_assistant_is_carried_in_not_dropped():
    """The budget cut can start the history at a reply. The template wants the
    user first — but that reply is still what the assistant said."""
    turns = [("assistant", "Object storage."), ("user", "And where is that configured?")]

    fixed = alternating_turns(turns)

    assert fixed[0][0] == "user"
    assert "Object storage." in fixed[0][1]
    assert "And where is that configured?" in fixed[0][1]
    assert len(fixed) == 1


def test_blank_messages_do_not_break_the_pairs_around_them():
    """The adapter used to drop empties, which made their neighbours adjacent."""
    turns = [("user", "Q1"), ("assistant", "   "), ("user", "Q2"), ("assistant", "A2")]

    fixed = alternating_turns(turns)

    assert [role for role, _ in fixed] == ["user", "assistant"]
    assert fixed[0][1] == "Q1\n\nQ2"


def test_the_result_always_alternates_and_starts_with_the_user():
    messy = [
        ("assistant", "stray"),
        ("assistant", "another"),
        ("user", "q1"),
        ("user", "q2"),
        ("assistant", "a"),
        ("user", "q3"),
    ]

    fixed = alternating_turns(messy)

    assert fixed[0][0] == "user"
    roles = [role for role, _ in fixed]
    assert all(a != b for a, b in zip(roles, roles[1:])), roles


# --- the history that precedes a fresh question --------------------------------


def test_history_never_ends_with_a_user_turn():
    """The question being asked now is a user message; two in a row is the 400."""
    turns = [("user", "q1"), ("assistant", "a1"), ("user", "q2 that never got an answer")]

    history = turns_before_user_message(turns)

    assert [role for role, _ in history] == ["user", "assistant"]


def test_a_lone_unanswered_question_leaves_no_history_at_all():
    assert turns_before_user_message([("user", "the only turn")]) == []


def test_nothing_in_nothing_out():
    assert turns_before_user_message(None) == []
    assert alternating_turns([]) == []


# --- what holding a model costs, said before the wait rather than after --------


def test_the_expected_cost_is_the_weights_plus_the_cache_we_chose():
    from app.core.domain.context_window_choice import expected_memory_bytes

    gb = 1024**3
    # Mistral 7B Q4_K_M, the model in the screenshot: 4.4 GB of weights, and a
    # KV cache of 131,072 bytes per token at the 8k window we pick on a laptop.
    at_8k = expected_memory_bytes(
        model_file_bytes=int(4.4 * gb), kv_bytes_per_token=131_072, context_window=8192
    )
    at_32k = expected_memory_bytes(
        model_file_bytes=int(4.4 * gb), kv_bytes_per_token=131_072, context_window=32768
    )

    assert round(at_8k / gb, 1) == 5.4
    assert round(at_32k / gb, 1) == 8.4
    # A bigger window costs more, and the difference is only the cache.
    assert at_32k - at_8k == 131_072 * (32768 - 8192)


def test_an_unknown_model_costs_nothing_it_can_claim():
    from app.core.domain.context_window_choice import expected_memory_bytes

    assert expected_memory_bytes(
        model_file_bytes=0, kv_bytes_per_token=0, context_window=0
    ) == 0
