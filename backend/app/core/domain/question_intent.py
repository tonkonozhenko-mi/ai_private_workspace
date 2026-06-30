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
