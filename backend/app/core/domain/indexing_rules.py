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
