"""Generate the deterministic wiki-export corpus.

The other external corpora are real repositories; a real company wiki cannot be
published, so this one is synthetic — a fictional payments platform's knowledge
base written in the shape real exports have: bracketed-tag titles
(``[ADR-07] …``, ``[Capability] …``), decision records, cross-page links, a
stale page other pages still reference, and a companion asset folder named
after its page. Deterministic by construction (no randomness, no timestamps in
content), so the corpus never drifts under the pre-registered questions; a test
pins its content hash.

Usage: ``python -m eval.make_wiki_corpus`` (writes to build/eval-corpora/wiki-export).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Every page: (relative path, title line, body). Markdown keeps the eval focused
# on retrieval; the HTML/extractor path has its own unit tests. The naming and
# linking SHAPE is what mirrors a real export.
_PAGES: tuple[tuple[str, str, str], ...] = (
    (
        "wiki/[ADR-01]_Service_split.md",
        "[ADR-01] Service split",
        "## Status\nAccepted, 2023-04.\n\n## Decision\nThe platform is split into an"
        " **invoice service** and a **ledger service** communicating over a queue."
        " A single monolith was rejected because invoice spikes must not delay ledger"
        " writes.\n\nSee [[ADR-03] Queue technology]([ADR-03]_Queue_technology.md) for"
        " the transport and [[Capability] Ledger]([Capability]_Ledger.md) for the"
        " consumer.\n",
    ),
    (
        "wiki/[ADR-02]_Invoice_numbering.md",
        "[ADR-02] Invoice numbering",
        "## Status\nAccepted.\n\n## Decision\nInvoice numbers are issued from a"
        " **per-tenant monotonic sequence** stored in Postgres, prefixed with the"
        " tenant short code (for example `ACME-000123`). UUIDs were rejected because"
        " accountants read these numbers over the phone.\n\nImplementation notes live"
        " in [[Capability] Invoicing]([Capability]_Invoicing.md).\n",
    ),
    (
        "wiki/[ADR-03]_Queue_technology.md",
        "[ADR-03] Queue technology",
        "## Status\nAccepted, revisit at 50k msg/s.\n\n## Decision\nRabbitMQ over"
        " Kafka: the team runs at thousands of messages per second, not millions, and"
        " operational simplicity wins. Dead-letter queues hold poison messages for"
        " manual replay — the procedure is in"
        " [[Runbook] Poison messages]([Runbook]_Poison_messages.md).\n",
    ),
    (
        "wiki/[ADR-04]_Tenant_isolation.md",
        "[ADR-04] Tenant isolation",
        "## Status\nAccepted.\n\n## Decision\nRow-level isolation with a mandatory"
        " `tenant_id` on every table, enforced by a Postgres RLS policy. Separate"
        " databases per tenant were rejected as an operational burden at our tenant"
        " count. The audit implications are described in"
        " [[Capability] Audit trail]([Capability]_Audit_trail.md).\n",
    ),
    (
        "wiki/[ADR-05]_Report_storage.md",
        "[ADR-05] Report storage",
        "## Status\n**Superseded by [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md).**\n\n"
        "## Decision (historical)\nMonthly statements were rendered to PDF and stored"
        " on the application server's local disk under `/var/reports`. Chosen for"
        " speed of delivery in the pilot.\n",
    ),
    (
        "wiki/[ADR-08]_Report_storage_v2.md",
        "[ADR-08] Report storage v2",
        "## Status\nAccepted, supersedes [[ADR-05] Report storage]([ADR-05]_Report_storage.md).\n\n"
        "## Decision\nStatements are stored in **object storage with lifecycle"
        " rules**: hot for 90 days, then archived, deleted after seven years per the"
        " retention schedule in [[Policy] Data retention]([Policy]_Data_retention.md)."
        " Local-disk storage failed the second data-centre migration.\n",
    ),
    (
        "wiki/[Capability]_Invoicing.md",
        "[Capability] Invoicing",
        "The invoice service issues, corrects and voids invoices. Numbering follows"
        " [[ADR-02] Invoice numbering]([ADR-02]_Invoice_numbering.md). Corrections"
        " never mutate an issued invoice: a credit note referencing the original is"
        " issued instead, which keeps the ledger append-only.\n\nThe review flow is"
        " illustrated in the attached diagram (see the"
        " `[Capability]_Invoicing_files/` folder).\n",
    ),
    (
        "wiki/[Capability]_Invoicing_files/invoice-flow.drawio",
        "",
        '<mxfile><diagram name="invoice-flow"><mxGraphModel><root>'
        '<mxCell id="a" value="Draft" vertex="1"/><mxCell id="b" value="Review" vertex="1"/>'
        '<mxCell id="c" value="Issued" vertex="1"/><mxCell id="d" value="Credit note" vertex="1"/>'
        '<mxCell id="e" value="approve" edge="1" source="a" target="b"/>'
        '<mxCell id="f" value="issue" edge="1" source="b" target="c"/>'
        '<mxCell id="g" value="correct" edge="1" source="c" target="d"/>'
        "</root></mxGraphModel></diagram></mxfile>",
    ),
    (
        "wiki/[Capability]_Ledger.md",
        "[Capability] Ledger",
        "The ledger service consumes payment events from the queue chosen in"
        " [[ADR-03] Queue technology]([ADR-03]_Queue_technology.md) and records"
        " double-entry postings. Every posting carries the `tenant_id` required by"
        " [[ADR-04] Tenant isolation]([ADR-04]_Tenant_isolation.md). Postings are"
        " immutable; reversals are new postings flagged `reversal`.\n",
    ),
    (
        "wiki/[Capability]_Audit_trail.md",
        "[Capability] Audit trail",
        "Every state change emits an audit event: actor, tenant, before/after hash."
        " Events are written to a separate schema the application role can only"
        " INSERT into. Auditors get read-only access quarterly per"
        " [[Policy] Data retention]([Policy]_Data_retention.md).\n",
    ),
    (
        "wiki/[Runbook]_Poison_messages.md",
        "[Runbook] Poison messages",
        "When a message lands on the dead-letter queue three times: 1) capture it"
        " with the drain script, 2) file the payload hash in the incident channel,"
        " 3) replay after the fix with `replay --dlq ledger`. Never delete a poison"
        " message — the ledger in [[Capability] Ledger]([Capability]_Ledger.md) must"
        " account for every event.\n",
    ),
    (
        "wiki/[Policy]_Data_retention.md",
        "[Policy] Data retention",
        "Financial records: seven years. Audit events: seven years. Application"
        " logs: 30 days. Statement archives follow"
        " [[ADR-08] Report storage v2]([ADR-08]_Report_storage_v2.md). Tenant"
        " deletion requests purge everything except records under the legal hold.\n",
    ),
    (
        "wiki/[Onboarding]_Start_here.md",
        "[Onboarding] Start here",
        "New to the platform? Read [[ADR-01] Service split]([ADR-01]_Service_split.md)"
        " first, then [[Capability] Invoicing]([Capability]_Invoicing.md) and"
        " [[Capability] Ledger]([Capability]_Ledger.md). The decisions index below"
        " is the table of contents for everything else.\n",
    ),
)

# Filler pages give the corpus realistic bulk (retrieval must find the needle
# among plausible hay). Deterministic content, one topic each.
_FILLER_TOPICS = (
    ("Billing_FAQ", "Answers to common billing questions from support rotations."),
    ("Oncall_rotation", "How the weekly on-call rotation is scheduled and handed over."),
    ("Glossary", "Terms: posting, credit note, tenant, statement, drain, replay."),
    ("Meeting_notes_2024_Q1", "Quarterly planning notes; capacity and hiring."),
    ("Meeting_notes_2024_Q2", "Quarterly planning notes; migration progress."),
    ("Vendor_contacts", "Escalation contacts for the payment gateway and bank API."),
    ("Sandbox_environments", "How to request a sandbox tenant for integration tests."),
    ("Release_calendar", "Release trains ship Tuesdays; freeze windows quarter-end."),
    ("Support_playbook", "Severity definitions and first-response templates."),
    ("Brand_guidelines", "Statement PDF layout: logo placement and typography."),
    ("Legacy_importer", "The CSV importer for tenants migrating from spreadsheets."),
    ("API_rate_limits", "Public API rate limits per plan and how to raise them."),
)


def generate(root: Path) -> Path:
    """Write the corpus under ``root``; return the root. Idempotent."""
    wiki = root / "wiki"
    wiki.mkdir(parents=True, exist_ok=True)
    for rel_path, title, body in _PAGES:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = body if not title else f"# {title}\n\n{body}"
        path.write_text(content, encoding="utf-8")
    for name, summary in _FILLER_TOPICS:
        page = wiki / f"[Notes]_{name}.md"
        paragraphs = "\n\n".join(
            f"{summary} Section {i}: routine operational detail, kept deliberately"
            " mundane so genuine answers stand out only when a question truly"
            " belongs here."
            for i in range(1, 4)
        )
        page.write_text(f"# [Notes] {name.replace('_', ' ')}\n\n{paragraphs}\n", encoding="utf-8")
    manifest = root / "MANIFEST.md"
    manifest.write_text(
        "# wiki-export corpus\n\nGenerated by `python -m eval.make_wiki_corpus`."
        f"\nPages: {len(_PAGES) + len(_FILLER_TOPICS)}. Content hash: {content_hash()}\n",
        encoding="utf-8",
    )
    return root


def content_hash() -> str:
    """Stable hash over every page body — pinned by a test so the corpus can
    never drift under its pre-registered questions."""
    digest = hashlib.sha256()
    for rel_path, title, body in _PAGES:
        digest.update(rel_path.encode())
        digest.update(title.encode())
        digest.update(body.encode())
    for name, summary in _FILLER_TOPICS:
        digest.update(name.encode())
        digest.update(summary.encode())
    return digest.hexdigest()[:16]


def main() -> None:
    from eval.corpora import CORPORA

    root = generate(CORPORA["wiki-export"].local_path)
    print(f"wiki-export: generated at {root} (hash {content_hash()})")


if __name__ == "__main__":
    main()
