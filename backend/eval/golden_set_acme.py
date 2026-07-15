"""A second labelled golden set, written against the external demo repo under
``build/demo-project`` (the fictional *acme-payments-platform*).

The first golden set (``eval/golden_set.py``) is written against THIS repository —
a Python RAG desktop app. Retrieval that looks good on its own codebase can still
be tuned to that one domain, so this set points at a deliberately *different* kind
of project: a small AWS/Terraform + FastAPI + GitHub Actions payments platform. If
the abstention floor and hit-rate hold up here too, the numbers aren't just an
artefact of the app's own prose.

Same three classes and matching rules as the app set:

- ``project_precise``: the answer lives in specific file(s); ``expected_paths`` are
  matched as path suffixes/substrings, so at least one must appear in the top-k.
- ``project_broad``: an "about the whole project" question; any grounded answer
  counts (these lean on the handbook pseudo-document).
- ``should_abstain``: NOT about the project (chit-chat, world facts, arithmetic);
  the right behaviour is to abstain and return zero project sources.

Every ``expected_paths`` entry here refers to a real file in ``build/demo-project``;
``tests/test_golden_set_acme.py`` fails in CI if a label ever points at a file that
doesn't exist, so the set can't silently rot.
"""

from __future__ import annotations

from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
    QuestionCase,
)

# The repo these questions are written against, relative to the project root, so
# both the runner and the CI label-integrity test resolve the same target.
ACME_REPO_RELATIVE = "build/demo-project"


GOLDEN_SET_ACME: tuple[QuestionCase, ...] = (
    # --- project_precise ------------------------------------------------
    QuestionCase(
        "acme-pp-db-engine",
        "What database engine and version backs the ledger?",
        CLASS_PROJECT_PRECISE,
        ("terraform/main.tf",),
    ),
    QuestionCase(
        "acme-pp-db-multiaz",
        "Is the ledger database highly available across availability zones?",
        CLASS_PROJECT_PRECISE,
        ("terraform/main.tf",),
    ),
    QuestionCase(
        "acme-pp-tf-state",
        "Where is the Terraform state stored and how is it locked?",
        CLASS_PROJECT_PRECISE,
        ("terraform/backend.tf",),
    ),
    QuestionCase(
        "acme-pp-vpc-cidr",
        "What CIDR block is the VPC configured with?",
        CLASS_PROJECT_PRECISE,
        ("terraform/variables.tf",),
    ),
    QuestionCase(
        "acme-pp-api-replicas",
        "How many replicas does the payments API run by default?",
        CLASS_PROJECT_PRECISE,
        ("terraform/variables.tf",),
    ),
    QuestionCase(
        "acme-pp-payment-endpoint",
        "Which endpoint creates a payment intent?",
        CLASS_PROJECT_PRECISE,
        ("src/api/main.py",),
    ),
    QuestionCase(
        "acme-pp-default-currency",
        "What is the default currency for a new payment intent?",
        CLASS_PROJECT_PRECISE,
        ("src/api/main.py",),
    ),
    QuestionCase(
        "acme-pp-ledger-guard",
        "How does the ledger worker guard against non-positive amounts?",
        CLASS_PROJECT_PRECISE,
        ("src/workers/ledger.py",),
    ),
    QuestionCase(
        "acme-pp-deploy-trigger",
        "When does the production deploy run?",
        CLASS_PROJECT_PRECISE,
        (".github/workflows/deploy.yml",),
    ),
    QuestionCase(
        "acme-pp-pr-checks",
        "What runs on a pull request?",
        CLASS_PROJECT_PRECISE,
        (".github/workflows/tests.yml",),
    ),
    QuestionCase(
        "acme-pp-queue",
        "How do payments reach the ledger worker?",
        CLASS_PROJECT_PRECISE,
        ("docs/architecture.md",),
    ),
    QuestionCase(
        "acme-pp-compose-db",
        "What Postgres version does the local docker-compose stack run?",
        CLASS_PROJECT_PRECISE,
        ("docker-compose.yml",),
    ),
    # --- project_precise: the file kinds the indexer learned later (SQL
    # migrations, tests, Makefile targets, tabular data) — added 2026-07-13,
    # pre-registered before the first scored run that included them.
    QuestionCase(
        "acme-pp-orders-table",
        "Where is the orders table defined?",
        CLASS_PROJECT_PRECISE,
        ("db/migrations/V2__create_orders.sql",),
    ),
    QuestionCase(
        "acme-pp-order-status",
        "How was the order status column added to the schema?",
        CLASS_PROJECT_PRECISE,
        ("db/migrations/V10__add_order_status.sql",),
    ),
    QuestionCase(
        "acme-pp-run-tests",
        "How do I run the tests for this project?",
        CLASS_PROJECT_PRECISE,
        ("Makefile", ".github/workflows/tests.yml"),
    ),
    QuestionCase(
        "acme-pp-ledger-test",
        "Which test covers the ledger worker's amount validation?",
        CLASS_PROJECT_PRECISE,
        ("tests/test_ledger.py",),
    ),
    QuestionCase(
        "acme-pp-costs",
        "What monthly infrastructure costs are recorded, and where?",
        CLASS_PROJECT_PRECISE,
        ("finance/costs.csv",),
    ),
    # Cyrillic case: the retrieval corpus is English; the user asks in Ukrainian.
    # Script-aware token budgeting (#234) made this class measurable end to end.
    QuestionCase(
        "acme-pp-cyrillic-backend",
        "Де налаштований Terraform backend і що зберігає стейт?",
        CLASS_PROJECT_PRECISE,
        ("terraform/backend.tf",),
    ),
    # --- project_broad --------------------------------------------------
    QuestionCase("acme-pb-what", "What is this project about?", CLASS_PROJECT_BROAD),
    QuestionCase(
        "acme-pb-stack",
        "What technologies and cloud services does this platform use?",
        CLASS_PROJECT_BROAD,
    ),
    QuestionCase(
        "acme-pb-envs", "What deployment environments does the platform have?", CLASS_PROJECT_BROAD
    ),
    QuestionCase("acme-pb-arch", "Give me an overview of the architecture.", CLASS_PROJECT_BROAD),
    # --- should_abstain (NOT about the project) -------------------------
    QuestionCase("acme-sa-time", "What time is it?", CLASS_SHOULD_ABSTAIN),
    # acme-sa-capital retired 2026-07-15: verbatim calibration probe (see golden_set.py).
    QuestionCase(
        "acme-sa-president", "Who is the president of Brazil?", CLASS_SHOULD_ABSTAIN
    ),
    QuestionCase("acme-sa-hello", "Hello, how are you doing?", CLASS_SHOULD_ABSTAIN),
    QuestionCase("acme-sa-math", "What is 17 times 23?", CLASS_SHOULD_ABSTAIN),
)


def golden_set_acme() -> tuple[QuestionCase, ...]:
    return GOLDEN_SET_ACME
