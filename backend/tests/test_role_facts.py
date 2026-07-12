"""Every role gets facts of its own — from the files, not from a model.

The old lenses reordered the same DevOps entities for everyone. These tests hold the
new promise: a DBA sees the schema, a tester sees the suites, an analyst sees the
endpoints, a developer sees the modules of whatever language the project is in — and
none of it is invented.
"""

from app.core.domain.api_surface import build_api_surface
from app.core.domain.js_modules import build_js_facts
from app.core.domain.ownership import build_ownership_facts
from app.core.domain.project_graph import EntityType, RelationType
from app.core.domain.project_graph_builder import build_project_graph
from app.core.domain.role_lens import role_lens_for
from app.core.domain.sql_schema import (
    build_sql_schema,
    orphan_tables,
    tables_without_primary_key,
    unindexed_foreign_keys,
)
from app.core.domain.starter_questions import starter_questions
from app.core.domain.test_suites import build_test_facts, is_test_file

_SQL = [
    (
        "db/migrations/V1__users.sql",
        """
        -- the first migration
        CREATE TABLE IF NOT EXISTS public.users (
            id BIGSERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL
        );
        CREATE UNIQUE INDEX idx_users_email ON users (email);
        """,
    ),
    (
        "db/migrations/V10__orders.sql",
        """
        CREATE TABLE `orders` (
          `id` INT NOT NULL,
          `user_id` INT NOT NULL REFERENCES users(id),
          `total` numeric(10,2),
          PRIMARY KEY (`id`)
        );
        CREATE TABLE audit_log (id bigint, message text);
        ALTER TABLE orders ADD COLUMN shipped_at timestamptz;
        """,
    ),
]


def test_the_schema_is_read_from_the_ddl():
    schema = build_sql_schema(_SQL)
    assert [t.name for t in schema.tables] == ["audit_log", "orders", "users"]
    orders = schema.table("orders")
    assert [c.name for c in orders.columns] == ["id", "user_id", "total"]
    assert orders.primary_key == ["id"]
    assert [(fk.from_table, fk.to_table) for fk in schema.foreign_keys] == [("orders", "users")]
    assert [i.name for i in schema.indexes] == ["idx_users_email"]


def test_migrations_are_ordered_the_way_the_tool_will_apply_them():
    # V10 must come after V1 — string sorting would put it first, and a DBA reading
    # the wrong order would draw the wrong conclusion.
    schema = build_sql_schema(_SQL)
    assert [m.path.rsplit("/", 1)[-1] for m in schema.migrations] == [
        "V1__users.sql",
        "V10__orders.sql",
    ]
    assert schema.migrations[1].alters == ["orders"]


def test_schema_findings_are_facts_not_verdicts():
    schema = build_sql_schema(_SQL)
    assert tables_without_primary_key(schema) == ["audit_log"]
    assert orphan_tables(schema) == ["audit_log"]
    assert unindexed_foreign_keys(schema) == ["orders"]  # orders has an FK, no index


def test_the_schema_reaches_the_graph_with_its_relationships():
    graph = build_project_graph("ws-1", sql_schema=build_sql_schema(_SQL))
    tables = {e.name for e in graph.entities_of_type(EntityType.TABLE)}
    assert {"users", "orders", "audit_log"} <= tables
    references = graph.relations_of_type(RelationType.REFERENCES)
    assert any("orders" in r.source_entity_id and "users" in r.target_entity_id for r in references)
    assert graph.entities_of_type(EntityType.MIGRATION)
    assert "sql" in graph.analyzers_run


def test_tests_are_found_with_how_to_run_them():
    files = {
        "backend/tests/test_orders.py": (
            "import pytest\n\ndef test_total():\n    assert 1\n\n"
            "@pytest.mark.skip\ndef test_refund():\n    assert 1\n"
        ),
        "Makefile": "test:\n\tpytest -q\n",
        "app/services/billing.py": "def charge():\n    return True\n",
    }
    facts = build_test_facts(files, source_paths=["app/services/billing.py"])
    assert [s.path for s in facts.suites] == ["backend/tests"]
    assert facts.frameworks == ["pytest"]
    assert facts.test_cases == 2
    assert facts.skipped_cases == 1
    # The project's own command comes before the framework default.
    assert facts.run_commands[0] == "make test"


def test_production_code_named_like_a_test_is_not_counted_as_one():
    """`test_helpers.py` in a source package is production code. Counting it would
    inflate the very numbers a tester relies on."""
    content = "def test_connection():\n    return db.ping()\n"
    assert is_test_file("app/db/test_helpers.py", content) is False
    assert is_test_file("tests/test_db.py", content) is True


def test_a_typescript_project_gets_modules_and_a_framework():
    files = {
        "package.json": '{"name":"shop","dependencies":{"react":"18"},"scripts":{"test":"vitest"}}',
        "src/main.tsx": "import { App } from './App';\n",
        "src/App.tsx": "import { Cart } from './components/Cart';\nexport function App() {}\n",
        "src/components/Cart.tsx": "export function Cart() {}\n",
    }
    facts = build_js_facts(files)
    assert facts.package_name == "shop"
    assert facts.frameworks == ["React"]
    assert facts.entrypoints == ["src/main.tsx"]
    app = next(m for m in facts.modules if m.name == "src/App")
    assert "components/Cart" in app.internal_imports

    graph = build_project_graph("ws-1", javascript=facts)
    apps = graph.entities_of_type(EntityType.APPLICATION)
    assert any(e.name == "React application" for e in apps)
    assert graph.entities_of_type(EntityType.MODULE)


def test_the_api_surface_is_the_verbs_the_system_offers():
    files = {
        "app/api/routes/orders.py": (
            '@router.post("/orders")\n'
            "def create_order():\n    ...\n\n"
            '@router.get("/orders/{order_id}")\n'
            "def get_order():\n    ...\n"
        ),
        "app/domain/models.py": (
            "class Order(BaseModel):\n    id: int\n\n"
            "class OrderRepository:\n    pass\n\n"
            "class CreateOrderRequest(BaseModel):\n    id: int\n"
        ),
    }
    surface = build_api_surface(files)
    assert [e.label for e in surface.endpoints] == ["POST /orders", "GET /orders/{order_id}"]
    assert surface.endpoints[0].handler == "create_order"
    assert surface.resources == ["orders"]
    # The nouns of the business — not its plumbing or its wire formats.
    assert surface.domain_entities == ["Order"]


def test_ownership_names_where_the_knowledge_is_concentrated():
    facts = build_ownership_facts(
        [
            ("app/billing.py", 20, [("Ada", 20)]),
            ("app/ui.py", 10, [("Ada", 5), ("Grace", 5)]),
            ("app/rare.py", 1, [("Ada", 1)]),  # below the activity floor
        ]
    )
    assert [f.path for f in facts.files] == ["app/billing.py", "app/ui.py"]
    assert [f.path for f in facts.single_owner_files] == ["app/billing.py"]
    assert facts.bus_factor == 1
    assert facts.key_people == [("Ada", 1)]


def test_each_lens_leads_with_its_own_facts():
    """The point of the whole exercise: a tester's first entity type is a test suite,
    not a pipeline; a DBA's is a table."""
    assert role_lens_for("tester").priority_entity_types[0] == EntityType.TEST_SUITE
    assert role_lens_for("dba").priority_entity_types[0] == EntityType.TABLE
    assert role_lens_for("business_analyst").priority_entity_types[0] == EntityType.API_ENDPOINT
    assert role_lens_for("developer").priority_entity_types[0] == EntityType.APPLICATION
    assert role_lens_for("devops").priority_entity_types[0] == EntityType.INFRA_COMPONENT


def test_the_dba_role_exists_end_to_end():
    lens = role_lens_for("dba")
    assert lens.label == "DBA"
    questions = starter_questions(None, lens)
    assert any("table" in q.lower() for q in questions)
    assert questions != starter_questions(None, role_lens_for("tester"))


def test_sql_files_are_still_indexed_and_still_answerable():
    """Giving SQL its own detected type must not quietly drop it from the index —
    'where is the orders table defined' has to keep working."""
    from app.core.use_cases.index_workspace import INDEXABLE_FILE_TYPES

    assert "sql" in INDEXABLE_FILE_TYPES


def test_a_project_without_sql_or_tests_still_gets_a_map():
    """No SQL is not an error; it is a project with no SQL."""
    graph = build_project_graph("ws-1", sql_schema=build_sql_schema([]))
    assert graph.entities_of_type(EntityType.TABLE) == []
    assert "sql" not in graph.analyzers_run
