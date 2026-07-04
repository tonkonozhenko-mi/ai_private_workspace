"""When retrieval finds nothing confident, the general-chat prompt must tell the
model to abstain on project-specific questions instead of inventing details."""

from app.core.domain.rag_prompt import build_general_chat_prompt


def test_abstention_clause_present_when_context_missing():
    prompt = build_general_chat_prompt(
        "where is the database configured", project_context_missing=True
    )
    low = prompt.lower()
    assert "indexed project" in low
    assert "do not guess project details" in low
    # It should NOT assert (falsely) that the user is making general conversation.
    assert "general conversation that is not about their project" not in low
    # Live-observed failure: the model told the user "I don't have real-time
    # access to your project files" — the opposite of what the product does.
    # The prompt must explicitly forbid that framing.
    assert "never claim you 'don't have access to'" in low


def test_no_abstention_clause_for_plain_chat():
    prompt = build_general_chat_prompt("hi there", project_context_missing=False)
    low = prompt.lower()
    assert "do not guess project details" not in low
    assert "general conversation that is not about their project" in low
