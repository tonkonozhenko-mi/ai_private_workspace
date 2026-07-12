"""The demo project must have something for every role to find.

It used to be a DevOps repository: Terraform, a pipeline, two Python files. So a
tester opening it found no tests, a DBA found no schema, and the app looked empty
to four of its six roles — not because the analyzers were broken, but because
there was nothing there. These pin the fixtures that make the demo honest.
"""

from pathlib import Path

from app.core.domain.sql_schema import (
    build_sql_schema,
    tables_without_primary_key,
    unindexed_foreign_keys,
)
from app.core.domain.test_suites import build_test_facts

_DEMO = Path(__file__).resolve().parents[2] / "build" / "demo-project"


def _sql_files() -> list[tuple[str, str]]:
    return [
        (str(path.relative_to(_DEMO)), path.read_text(encoding="utf-8"))
        for path in sorted(_DEMO.rglob("*.sql"))
    ]


def test_the_demo_has_a_schema_a_dba_would_recognise():
    schema = build_sql_schema(_sql_files())
    names = {table.name for table in schema.tables}
    assert {"customers", "orders", "order_events"} <= names
    assert any(fk.to_table == "customers" for fk in schema.foreign_keys)
    # And the two facts the DBA lens leads with, present on purpose:
    assert "order_events" in unindexed_foreign_keys(schema)
    assert "order_events" in tables_without_primary_key(schema)


def test_the_migrations_run_in_number_order_not_alphabetical_order():
    """V10 after V3 — the whole point of the fixture. Sorted as text, V10 would
    run second and ALTER a table that does not exist yet."""
    schema = build_sql_schema(_sql_files())
    order = [Path(migration.path).name for migration in schema.migrations]
    assert order == [
        "V1__create_customers.sql",
        "V2__create_orders.sql",
        "V3__add_indexes.sql",
        "V10__add_order_status.sql",
    ]


def test_the_demo_has_tests_a_tester_would_recognise():
    files = {
        str(path.relative_to(_DEMO)): path.read_text(encoding="utf-8")
        for path in sorted(_DEMO.rglob("*.py"))
    }
    facts = build_test_facts(files, source_paths=list(files))
    assert facts.suites, "the demo project must contain at least one test suite"
    assert "pytest" in facts.frameworks
    assert facts.test_cases >= 4
    assert facts.skipped_cases >= 1  # a skipped case, so the count means something


def test_the_demo_says_how_to_run_its_tests():
    assert "test:" in (_DEMO / "Makefile").read_text(encoding="utf-8")


def test_the_demo_has_documents_and_a_spreadsheet_to_index():
    assert (_DEMO / "docs" / "runbook.docx").is_file()
    assert (_DEMO / "finance" / "costs.csv").is_file()
