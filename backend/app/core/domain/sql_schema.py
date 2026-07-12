"""The data model a project writes down in its SQL.

A DBA opening a strange repository asks three things: what tables exist, how they
reference each other, and in what order the migrations got them here. All three are
written in the DDL — nobody has to guess, and no model has to hallucinate. This
module reads them out.

Deliberately regex, not a real SQL parser: the file may be a Postgres dump, a MySQL
migration, or a fragment; a strict parser would choke on the first dialect quirk and
we would learn nothing. Approximate-but-honest beats exact-but-absent. Every fact
here is traceable to a file, and anything we cannot read we simply do not claim.

Pure: no I/O, no state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# CREATE TABLE [IF NOT EXISTS] [schema.]name ( … ) — the body is captured by
# balancing parentheses in _table_body, not by regex, because column definitions
# nest them (numeric(10,2), CHECK (x > 0)).
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>[\w.\"`\[\]]+)\s*\(",
    re.IGNORECASE,
)
_CREATE_VIEW_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>[\w.\"`\[\]]+)",
    re.IGNORECASE,
)
_CREATE_INDEX_RE = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<name>[\w.\"`\[\]]+)\s+ON\s+(?P<table>[\w.\"`\[\]]+)",
    re.IGNORECASE,
)
# Inline (column-level) and table-level REFERENCES, plus the ALTER TABLE … ADD
# CONSTRAINT … FOREIGN KEY form that migrations prefer.
_REFERENCES_RE = re.compile(r"REFERENCES\s+(?P<table>[\w.\"`\[\]]+)", re.IGNORECASE)
_ALTER_ADD_FK_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?P<table>[\w.\"`\[\]]+).{0,400}?"
    r"FOREIGN\s+KEY\s*\((?P<column>[^)]+)\)\s*REFERENCES\s+(?P<target>[\w.\"`\[\]]+)",
    re.IGNORECASE | re.DOTALL,
)
_ALTER_ADD_COLUMN_RE = re.compile(
    r"ALTER\s+TABLE\s+(?:ONLY\s+)?(?P<table>[\w.\"`\[\]]+)\s+ADD\s+(?:COLUMN\s+)?"
    r"(?:IF\s+NOT\s+EXISTS\s+)?(?P<column>[\w\"`\[\]]+)",
    re.IGNORECASE,
)
_DROP_TABLE_RE = re.compile(
    r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?P<name>[\w.\"`\[\]]+)", re.IGNORECASE
)

# Words that begin a table-level constraint rather than a column.
_CONSTRAINT_WORDS = {
    "primary",
    "foreign",
    "unique",
    "check",
    "constraint",
    "exclude",
    "like",
    "partition",
}

_MIGRATION_DIR_HINTS = ("migration", "migrations", "changelog", "versions", "schema")


def _clean(identifier: str) -> str:
    """`"public"."orders"` / `[dbo].[Orders]` / `` `orders` `` → `orders`.

    The schema qualifier is dropped on purpose: a repository almost never has two
    tables with the same name in different schemas, and keeping it would make the
    same table look like two different ones across dialects.
    """
    name = identifier.strip().strip(";,")
    name = re.sub(r"[\"`\[\]]", "", name)
    return name.split(".")[-1].lower()


def _strip_noise(sql: str) -> str:
    """Comments and string literals removed, so a `-- REFERENCES orders` in prose or
    an 'insert into' inside a string never invents a table."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


@dataclass(frozen=True)
class SqlColumn:
    name: str
    data_type: str
    is_primary_key: bool = False
    is_nullable: bool = True


@dataclass(frozen=True)
class SqlForeignKey:
    from_table: str
    from_column: str | None
    to_table: str
    source_file: str


@dataclass(frozen=True)
class SqlTable:
    name: str
    columns: list[SqlColumn] = field(default_factory=list)
    source_file: str = ""
    is_view: bool = False

    @property
    def primary_key(self) -> list[str]:
        return [column.name for column in self.columns if column.is_primary_key]


@dataclass(frozen=True)
class SqlIndex:
    name: str
    table: str
    unique: bool
    source_file: str


@dataclass(frozen=True)
class SqlMigration:
    """One migration file, in the order the project will apply it.

    ``order_key`` is what the sorted() call sees — a numeric prefix when the file has
    one (V3__, 0003_, 20240115_), otherwise the path. That is exactly how Flyway,
    Alembic and Liquibase decide, so we don't invent a different truth.
    """

    path: str
    order_key: str
    creates: list[str] = field(default_factory=list)
    drops: list[str] = field(default_factory=list)
    alters: list[str] = field(default_factory=list)


def _table_body(sql: str, open_paren_index: int) -> str:
    """The text between the CREATE TABLE parentheses, matched by balancing them."""
    depth = 0
    for index in range(open_paren_index, len(sql)):
        char = sql[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return sql[open_paren_index + 1 : index]
    return ""


def _split_definitions(body: str) -> list[str]:
    """Split a table body on top-level commas — numeric(10,2) must stay one piece."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _parse_columns(body: str) -> tuple[list[SqlColumn], list[str]]:
    """Columns of one table, plus the tables its inline REFERENCES point at."""
    columns: list[SqlColumn] = []
    referenced: list[str] = []
    inline_primary_keys: list[str] = []

    for definition in _split_definitions(body):
        first_word = definition.split()[0].strip("(").lower() if definition.split() else ""
        cleaned_first = re.sub(r"[\"`\[\]]", "", first_word)

        for match in _REFERENCES_RE.finditer(definition):
            referenced.append(_clean(match.group("table")))

        if cleaned_first in _CONSTRAINT_WORDS:
            # A table-level PRIMARY KEY (a, b) names columns defined above.
            if cleaned_first in {"primary", "constraint"} and re.search(
                r"PRIMARY\s+KEY", definition, re.IGNORECASE
            ):
                inside = re.search(r"PRIMARY\s+KEY\s*\(([^)]*)\)", definition, re.IGNORECASE)
                if inside:
                    inline_primary_keys += [
                        _clean(part) for part in inside.group(1).split(",") if part.strip()
                    ]
            continue

        tokens = definition.split()
        if len(tokens) < 2:
            continue
        name = _clean(tokens[0])
        data_type = tokens[1].rstrip(",").split("(")[0].lower()
        columns.append(
            SqlColumn(
                name=name,
                data_type=data_type,
                is_primary_key=bool(re.search(r"PRIMARY\s+KEY", definition, re.IGNORECASE)),
                is_nullable=not re.search(r"NOT\s+NULL", definition, re.IGNORECASE),
            )
        )

    if inline_primary_keys:
        columns = [
            SqlColumn(
                name=column.name,
                data_type=column.data_type,
                is_primary_key=column.is_primary_key or column.name in inline_primary_keys,
                is_nullable=column.is_nullable,
            )
            for column in columns
        ]
    return columns, referenced


@dataclass(frozen=True)
class SqlSchema:
    tables: list[SqlTable] = field(default_factory=list)
    foreign_keys: list[SqlForeignKey] = field(default_factory=list)
    indexes: list[SqlIndex] = field(default_factory=list)
    migrations: list[SqlMigration] = field(default_factory=list)

    def table(self, name: str) -> SqlTable | None:
        lowered = name.lower()
        return next((t for t in self.tables if t.name == lowered), None)


def parse_sql_file(
    path: str, content: str
) -> tuple[list[SqlTable], list[SqlForeignKey], list[SqlIndex]]:
    """Tables, foreign keys and indexes declared in one .sql file."""
    sql = _strip_noise(content)
    tables: list[SqlTable] = []
    foreign_keys: list[SqlForeignKey] = []
    indexes: list[SqlIndex] = []

    for match in _CREATE_TABLE_RE.finditer(sql):
        name = _clean(match.group("name"))
        body = _table_body(sql, match.end() - 1)
        columns, referenced = _parse_columns(body)
        tables.append(SqlTable(name=name, columns=columns, source_file=path))
        for target in referenced:
            foreign_keys.append(
                SqlForeignKey(from_table=name, from_column=None, to_table=target, source_file=path)
            )

    for match in _CREATE_VIEW_RE.finditer(sql):
        tables.append(SqlTable(name=_clean(match.group("name")), source_file=path, is_view=True))

    for match in _CREATE_INDEX_RE.finditer(sql):
        indexes.append(
            SqlIndex(
                name=_clean(match.group("name")),
                table=_clean(match.group("table")),
                unique="UNIQUE" in match.group(0).upper(),
                source_file=path,
            )
        )

    for match in _ALTER_ADD_FK_RE.finditer(sql):
        foreign_keys.append(
            SqlForeignKey(
                from_table=_clean(match.group("table")),
                from_column=_clean(match.group("column")),
                to_table=_clean(match.group("target")),
                source_file=path,
            )
        )

    return tables, foreign_keys, indexes


def looks_like_migration(path: str) -> bool:
    lowered = path.lower()
    return any(f"/{hint}/" in f"/{lowered}" for hint in _MIGRATION_DIR_HINTS) or bool(
        re.match(r"^(v\d+|\d{3,})", lowered.rsplit("/", 1)[-1])
    )


def migration_order_key(path: str) -> str:
    """Flyway (V3__), Alembic/Django (0003_), timestamped (20240115_) — take the
    leading number and zero-pad it, so 10 sorts after 9 rather than before it."""
    name = path.rsplit("/", 1)[-1]
    match = re.match(r"^[vV]?(\d+)", name)
    if match:
        return match.group(1).zfill(20)
    return path


def build_sql_schema(files: list[tuple[str, str]]) -> SqlSchema:
    """The whole data model, from every .sql file in the project.

    ``files`` is [(path, content)]. Views and tables are keyed by name, so a table
    created in one migration and altered in three others appears once — with the
    file that created it as its home.
    """
    tables: dict[str, SqlTable] = {}
    foreign_keys: list[SqlForeignKey] = []
    indexes: list[SqlIndex] = []
    migrations: list[SqlMigration] = []

    for path, content in files:
        file_tables, file_fks, file_indexes = parse_sql_file(path, content)
        for table in file_tables:
            existing = tables.get(table.name)
            # A later ALTER shouldn't replace the CREATE that has the columns.
            if existing is None or (not existing.columns and table.columns):
                tables[table.name] = table
        foreign_keys += file_fks
        indexes += file_indexes

        if looks_like_migration(path):
            sql = _strip_noise(content)
            migrations.append(
                SqlMigration(
                    path=path,
                    order_key=migration_order_key(path),
                    creates=[_clean(m.group("name")) for m in _CREATE_TABLE_RE.finditer(sql)],
                    drops=[_clean(m.group("name")) for m in _DROP_TABLE_RE.finditer(sql)],
                    alters=sorted(
                        {_clean(m.group("table")) for m in _ALTER_ADD_COLUMN_RE.finditer(sql)}
                    ),
                )
            )

    # Only keep foreign keys whose target we actually saw declared: a REFERENCES to a
    # table defined in another system is not a fact about *this* project's schema.
    known = set(tables)
    foreign_keys = [fk for fk in foreign_keys if fk.to_table in known and fk.from_table in known]

    return SqlSchema(
        tables=sorted(tables.values(), key=lambda t: t.name),
        foreign_keys=sorted(foreign_keys, key=lambda fk: (fk.from_table, fk.to_table)),
        indexes=sorted(indexes, key=lambda i: (i.table, i.name)),
        migrations=sorted(migrations, key=lambda m: m.order_key),
    )


def orphan_tables(schema: SqlSchema) -> list[str]:
    """Tables nothing references and which reference nothing — often dead, sometimes
    the most important table in the system. We report, we don't judge."""
    connected: set[str] = set()
    for fk in schema.foreign_keys:
        connected.add(fk.from_table)
        connected.add(fk.to_table)
    return [t.name for t in schema.tables if not t.is_view and t.name not in connected]


def tables_without_primary_key(schema: SqlSchema) -> list[str]:
    return [t.name for t in schema.tables if not t.is_view and t.columns and not t.primary_key]


def unindexed_foreign_keys(schema: SqlSchema) -> list[str]:
    """Foreign keys with no index on the referencing table — the classic cause of a
    slow join and a locking DELETE. Reported as a fact, not a verdict: a small table
    doesn't care."""
    indexed = {index.table for index in schema.indexes}
    return sorted({fk.from_table for fk in schema.foreign_keys if fk.from_table not in indexed})
