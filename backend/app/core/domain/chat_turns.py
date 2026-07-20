"""Shaping a conversation into what a chat template will accept.

Mistral's template — and it is not alone — refuses anything but a strict
alternation that opens with the user:

    llama-server HTTP 400: "Conversation roles must alternate
    user/assistant/user/assistant..."

That is a template raising, not a model declining, so the whole answer is lost
and the person is told "the selected local model could not answer" — true, and
an explanation of nothing.

Maks hit this live on 16.07. It worked on the retry, so whatever produced the
bad sequence had cleared by then and I could not read the thread that caused it
(the conversation store lives on his machine). I am not going to name a cause I
did not see.

What I can name is where our own code is free to produce a sequence the template
hates, because these are in the file and provable:

1. The summary preface. When older turns are folded into a summary,
   ``history_for_prompt`` prepends it as ``("user", …)``. If the surviving turns
   then start with the user, that is two user messages in a row.
2. The budget cut. ``split_history_by_budget`` keeps the most recent turns that
   fit, and is free to begin the history at an assistant reply — the template
   wants the user first.
3. Dropped blanks. The adapter skipped empty messages, which removes one half of
   a pair and makes its neighbours adjacent.

Each is ordinary, none is exotic, and any of them is enough. So the rule is
applied once, on the way out, and it never discards what a person said:
consecutive messages of one role are joined rather than dropped, and a leading
assistant reply is carried in as quoted context rather than deleted for a
formality. Trimming a conversation is not the same as editing it.
"""

from __future__ import annotations

Turn = tuple[str, str]

# What a lone assistant message at the front is doing there: it is what the
# assistant said, and the template will not let it speak first.
_LEADING_ASSISTANT_PREFACE = "[Earlier in this conversation you said]"


def alternating_turns(turns: list[Turn] | None) -> list[Turn]:
    """The conversation as a chat template will accept it: user first, then
    strictly alternating, with nothing said by anyone thrown away."""
    if not turns:
        return []

    kept: list[Turn] = []
    for role, content in turns:
        text = (content or "").strip()
        if not text:
            continue
        normalized = "assistant" if role == "assistant" else "user"
        if kept and kept[-1][0] == normalized:
            # Two in a row: one message, both texts. Merging keeps every word;
            # dropping one would silently rewrite what was said.
            previous_role, previous_text = kept[-1]
            kept[-1] = (previous_role, f"{previous_text}\n\n{text}")
            continue
        kept.append((normalized, text))

    if kept and kept[0][0] == "assistant":
        # The template insists a conversation opens with the user. The reply is
        # still worth having, so it is carried in as quoted context rather than
        # deleted for a formality.
        role, text = kept[0]
        kept[0] = ("user", f"{_LEADING_ASSISTANT_PREFACE}\n{text}")
        if len(kept) > 1 and kept[1][0] == "user":
            merged_role, merged_text = kept[0]
            kept[0] = (merged_role, f"{merged_text}\n\n{kept[1][1]}")
            del kept[1]

    return kept


def turns_before_user_message(turns: list[Turn] | None) -> list[Turn]:
    """History for a request that ends in a fresh user question.

    The new question is a user message, so the history must not end with one —
    otherwise the pair we send is user, user. The last user turn is an unanswered
    question, and an unanswered question is context for the one being asked now.
    """
    kept = alternating_turns(turns)
    if kept and kept[-1][0] == "user":
        role, text = kept.pop()
        if kept:
            # Fold it into the assistant turn before it? No — that would put a
            # person's words in the assistant's mouth. Drop it from the history
            # and let the caller carry it: it is the immediately preceding
            # question, which the new question already follows from.
            return kept
        return [(role, text)][:0]
    return kept
