"""Pre-registered questions for the generated wiki-export corpus.

The corpus is synthetic (see ``make_wiki_corpus.py``) but the questions are the
real class a knowledge base gets asked: what did we decide, why, what replaced
what, and where is the procedure. ``expected_paths`` reference the generator's
own page paths; a test pins the corpus content hash so these can never drift
apart silently.
"""

from __future__ import annotations

from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
    QuestionCase,
)

GOLDEN_SET_WIKI: tuple[QuestionCase, ...] = (
    QuestionCase(
        "wiki-pp-numbering",
        "What did we decide about invoice numbering, and why not UUIDs?",
        CLASS_PROJECT_PRECISE,
        ("[ADR-02]_Invoice_numbering.md",),
    ),
    QuestionCase(
        "wiki-pp-queue",
        "Why was RabbitMQ chosen over Kafka?",
        CLASS_PROJECT_PRECISE,
        ("[ADR-03]_Queue_technology.md",),
    ),
    QuestionCase(
        "wiki-pp-superseded",
        "Where are monthly statements stored now, and what replaced the old approach?",
        CLASS_PROJECT_PRECISE,
        ("[ADR-08]_Report_storage_v2.md", "[ADR-05]_Report_storage.md"),
    ),
    QuestionCase(
        "wiki-pp-tenant",
        "How is tenant isolation enforced in the database?",
        CLASS_PROJECT_PRECISE,
        ("[ADR-04]_Tenant_isolation.md",),
    ),
    QuestionCase(
        "wiki-pp-poison",
        "What is the procedure when a message keeps failing and lands on the dead-letter queue?",
        CLASS_PROJECT_PRECISE,
        ("[Runbook]_Poison_messages.md",),
    ),
    QuestionCase(
        "wiki-pp-retention",
        "How long are financial records and audit events retained?",
        CLASS_PROJECT_PRECISE,
        ("[Policy]_Data_retention.md",),
    ),
    QuestionCase(
        "wiki-pp-corrections",
        "How are invoice corrections handled without mutating issued invoices?",
        CLASS_PROJECT_PRECISE,
        ("[Capability]_Invoicing.md",),
    ),
    QuestionCase(
        "wiki-pp-onboarding",
        "I'm new here — what should I read first?",
        CLASS_PROJECT_PRECISE,
        ("[Onboarding]_Start_here.md",),
    ),
    # Cyrillic case: the same knowledge base, asked in Ukrainian. Script-aware
    # budgeting (#234) made this class safe to measure; retrieval must cross the
    # language boundary because the pages are English.
    QuestionCase(
        "wiki-pp-cyrillic",
        "Чому для черги повідомлень обрали RabbitMQ, а не Kafka?",
        CLASS_PROJECT_PRECISE,
        ("[ADR-03]_Queue_technology.md",),
    ),
    QuestionCase("wiki-pb-what", "What is this knowledge base about?", CLASS_PROJECT_BROAD),
    QuestionCase(
        "wiki-pb-decisions",
        "What architectural decisions have been recorded?",
        CLASS_PROJECT_BROAD,
    ),
    QuestionCase("wiki-sa-pasta", "How do I cook pasta carbonara?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("wiki-sa-year", "What year is it?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("wiki-sa-joke", "Tell me a joke about programmers.", CLASS_SHOULD_ABSTAIN),
)


def golden_set_wiki() -> tuple[QuestionCase, ...]:
    return GOLDEN_SET_WIKI


# --- Mixed-group protocol (manual — see docs/BENCHMARKS.md) -----------------
# The group union spans two indexes, which this CLI harness does not drive yet.
# Until it does, these five cross-source questions are asked BY HAND in the app
# against a group of wiki-export + fastapi-template; an answer passes when it
# cites at least one source from EACH member.
MIXED_GROUP_QUESTIONS: tuple[str, ...] = (
    "What did we decide about where reports are stored, and where does the backend configure storage?",
    "Which decisions talk about the queue, and is there any queue in the code?",
    "How is tenant isolation described in the wiki, and how does the backend isolate users?",
    "What does the onboarding page say to read first, and where would a developer start in the code?",
    "What retention rules exist, and does anything in the code enforce a retention period?",
)
