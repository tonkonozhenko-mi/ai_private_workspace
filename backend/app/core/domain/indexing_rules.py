from dataclasses import dataclass
from datetime import UTC, datetime

DEFAULT_INDEXING_RULES_PROFILE = "balanced"
DEFAULT_INCLUDE_PATTERNS: tuple[str, ...] = (
    "src/**",
    "app/**",
    "backend/**",
    "frontend/src/**",
    "docs/**",
    "README*",
    "*.md",
    "*.py",
    "*.tf",
    "*.tfvars",
    "terragrunt.hcl",
    "*.yaml",
    "*.yml",
    "Dockerfile",
    "docker-compose*.yml",
    ".github/workflows/**",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "helm/**",
    "chart/**",
    "charts/**",
    # Documents. A project folder is not only code: runbooks in Word, cost sheets
    # in Excel, decisions in PDF, an exported wiki as HTML. All read locally.
    "*.docx",
    "*.xlsx",
    "*.pdf",
    "*.html",
    "*.htm",
    "*.txt",
    "*.rst",
    "*.adoc",
    "*.csv",
    "*.tsv",
    "*.ipynb",
    # Source code. Everything above this line was infrastructure, Python and docs —
    # which meant a TypeScript, Go or Java repository matched almost nothing and
    # answered almost nothing. These are the extensions a codebase is made of.
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.mjs",
    "*.cjs",
    "*.vue",
    "*.svelte",
    "*.java",
    "*.kt",
    "*.go",
    "*.rs",
    "*.rb",
    "*.php",
    "*.cs",
    "*.c",
    "*.h",
    "*.cpp",
    "*.hpp",
    "*.swift",
    "*.scala",
    "*.lua",
    "*.dart",
    "*.sql",
    "*.proto",
    "*.graphql",
    "*.sh",
    # Config that isn't YAML or JSON — pyproject.toml, setup.cfg, Makefile.
    "*.toml",
    "*.ini",
    "*.cfg",
    "*.properties",
    "*.conf",
    "*.xml",
    "Makefile",
    "*.mk",
    ".env.example",
    ".env.sample",
    ".env.template",
)
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    ".git/**",
    "node_modules/**",
    ".venv/**",
    "venv/**",
    "dist/**",
    "build/**",
    "coverage/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    "__pycache__/**",
    # Broad, depth-agnostic guards (fnmatch '*' spans '/') so dependency and
    # virtualenv folders are skipped even when nested (e.g. backend/.venv-x86_64,
    # */site-packages). Without these, the AI ends up citing pip internals.
    "*.venv*",
    "*/venv/*",
    "*/venv-*/*",
    "*site-packages*",
    "*node_modules*",
    "*__pycache__*",
    "*.pytest_cache*",
    "*.mypy_cache*",
    "*.egg-info*",
    "*.tox*",
    "*.pyc",
    "*.log",
    "*.lock",
    # Machine-written files that would swamp a real codebase: dependency lockfiles
    # (tens of thousands of lines nobody reads), minified bundles and source maps,
    # and compiled output. The scanner refuses these by name as well — belt and
    # braces, because one committed bundle can outweigh the whole source tree.
    "package-lock.json",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "go.sum",
    "*.min.js",
    "*.min.css",
    "*.map",
    "out/**",
    "vendor/**",
    # A real .env holds credentials and must never be indexed. Its committed
    # templates (.env.example) are documentation and stay included above.
    ".env",
    ".env.local",
    "*/.env",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.zip",
    "*.tar",
    "*.gz",
)


@dataclass(frozen=True)
class IndexingRulesProfile:
    workspace_id: str
    profile: str = DEFAULT_INDEXING_RULES_PROFILE
    include_patterns: tuple[str, ...] = DEFAULT_INCLUDE_PATTERNS
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS
    updated_at: str | None = None

    @property
    def include_rules_count(self) -> int:
        return len(self.include_patterns)

    @property
    def exclude_rules_count(self) -> int:
        return len(self.exclude_patterns)


def default_indexing_rules(workspace_id: str) -> IndexingRulesProfile:
    return IndexingRulesProfile(
        workspace_id=workspace_id,
        updated_at=datetime.now(UTC).isoformat(),
    )


def normalize_patterns(patterns: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        value = pattern.strip()
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized[:80])
