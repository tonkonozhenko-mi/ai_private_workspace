"""Cheap, deterministic heuristic: does a question look project-specific?

Ask routes a question to "general conversation" when retrieval finds nothing
confident. That's right for chit-chat, but wrong (a hallucination vector) when
the question really was about the user's project — the model then invents file
names, services and config it never saw. This helper lets the caller tell the
two apart so it can abstain honestly on project questions while still answering
general ones. Pure regex; no model, no I/O.
"""

import re

# Signals that a question is about *this* codebase/infra rather than general
# knowledge: a backticked token, a real-looking file path/extension, or code/
# infra/ops nouns. Intentionally inclusive — a false positive only adds a
# "not found in your project" note, while a false negative lets a project
# question be answered ungrounded (the thing we want to avoid).
_PROJECT_SIGNAL = re.compile(
    r"`[^`]+`"
    r"|\b[\w./-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|c|cpp|cs|tf|tfvars|hcl|"
    r"ya?ml|json|toml|ini|cfg|sh|sql|md|env|dockerfile)\b"
    r"|\b(?:this|that|our|my|the)\s+(?:project|repo|repository|codebase|app|"
    r"application|service|module|package|pipeline|config|configuration|"
    r"deployment|infra(?:structure)?|setup|backend|frontend)\b"
    r"|\b(?:codebase|terraform|terragrunt|kubernetes|k8s|helm|dockerfile|"
    r"docker[- ]?compose|ci/?cd|gitlab[- ]?ci|github\s+actions|pipeline|"
    r"workflow|endpoint|env(?:ironment)?s?|migration|schema|deploy(?:ed|ment)?|"
    r"source\s+path|which\s+file|what\s+file|where\s+is)\b",
    re.IGNORECASE,
)


def looks_project_specific(question: str) -> bool:
    """True if the question appears to ask about the user's own project/infra."""
    return bool(_PROJECT_SIGNAL.search(question or ""))


# The inverse detector. ``looks_project_specific`` is deliberately leaky the SAFE
# way (a project question that looks generic still gets retrieval), but that means
# it says False for most real project questions ("how does X work?"), so it can't
# gate retrieval/routing on its own. Chit-chat, by contrast, is a small and regular
# class — greetings, time/weather, jokes, world trivia, arithmetic, "in general" —
# so detecting *that* is far more reliable. This routes obvious chit-chat straight
# to general conversation and lets the retrieval gates fire on everything else.
#
# HIGH PRECISION is the rule: a false positive (a real project question flagged as
# chat) skips retrieval and answers ungrounded, which is worse than over-abstaining.
# So patterns are specific, and any project signal wins outright (guard below).
_CHAT_SIGNAL = re.compile(
    r"\bhow are you\b|\bhow'?s it going\b|\bnice to meet you\b"
    r"|\bthat was (?:helpful|great|useful|awesome|nice)\b"
    r"|\bwhat time is it\b|\bwhat'?s? (?:is )?the (?:time|weather|date)\b|\bthe weather\b"
    r"|\b(?:tell|hear) (?:me )?a joke\b|\bmake me laugh\b"
    r"|\bcapital of\b|\bworld cup\b|\bwho won\b|\bolympics?\b|\bpopulation of\b"
    r"|\bpresident of\b|\bprime minister of\b|\bin general\b"
    r"|\b(?:carbonara|recipe|pizza|pasta|omelette|risotto|espresso|cappuccino|smoothie)\b",
    re.IGNORECASE,
)
# Two numbers joined by an arithmetic operator ("17 times 23", "5 + 4").
_ARITHMETIC = re.compile(
    r"\b\d+\s*(?:[-+*x×]|times|plus|minus|multiplied by|divided by)\s*\d+\b",
    re.IGNORECASE,
)
# The WHOLE message is a bare greeting/thanks — matched only when it stands alone,
# so "Hi, how does X work?" (a project question with a greeting prefix) is NOT chat.
_SOCIAL_ONLY = re.compile(
    r"^\s*(?:hi|hey|hello+|yo|sup|greetings|thanks|thanks a lot|thank you|"
    r"thank you very much|thx|cheers|good (?:morning|afternoon|evening|night))"
    r"[\s!.,'’?]*$",
    re.IGNORECASE,
)


def looks_general_chat(question: str) -> bool:
    """True if the question is obvious non-project chit-chat (greeting, world fact,
    time/weather, joke, arithmetic, "in general" aside). High precision by design:
    any project signal makes it False, and bare greetings only count when they are
    the entire message."""
    q = question or ""
    if looks_project_specific(q):
        return False
    return bool(_CHAT_SIGNAL.search(q) or _ARITHMETIC.search(q) or _SOCIAL_ONLY.match(q))
