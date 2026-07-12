"""What counts as source code, what counts as config, and what is junk.

The index used to know only the languages the analyzers knew: Python, Terraform,
YAML, CI files. A TypeScript repository — the most common kind of repository there
is — was scanned, found "unknown" everywhere, and answered nothing. This module is
the deterministic vocabulary that fixes that: extension → type, and a short list of
things that look like code but are actually machine output.

Pure: no I/O, no state. The file-system adapter uses it to label a file, the index
use case uses it to refuse one.
"""

from __future__ import annotations

from pathlib import PurePosixPath

SOURCE_CODE = "source_code"
CONFIG = "config"
XML_CONFIG = "xml_config"
MAKEFILE = "makefile"
# SQL is source code, but it is also the only place a project writes down its data
# model. Giving it its own type lets the schema analyzer find it — and stops a
# migrations folder from making a Java service introduce itself as "SQL application".
SQL = "sql"

# Extension → the language a human would name. The value is only used for the
# label ("TypeScript application"), so keep it human, not machine.
SOURCE_CODE_LANGUAGES: dict[str, str] = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".gradle": "Gradle",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".c": "C",
    ".h": "C",
    ".swift": "Swift",
    ".scala": "Scala",
    ".lua": "Lua",
    ".pl": "Perl",
    ".r": "R",
    ".m": "Objective-C",
    ".dart": "Dart",
    ".proto": "Protobuf",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
}

SOURCE_CODE_EXTENSIONS = frozenset(SOURCE_CODE_LANGUAGES)

# Config formats that aren't YAML or JSON. pyproject.toml, setup.cfg, my.ini and
# friends answer "how is X configured" — the single most common question about a
# repository after "where is X".
CONFIG_EXTENSIONS = frozenset({".toml", ".ini", ".cfg", ".properties", ".conf", ".editorconfig"})

# A real .env holds secrets and must never be indexed; its committed *templates*
# are documentation and should be.
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")

# Machine-written files that would otherwise flood the index with noise: a single
# lockfile can be tens of thousands of lines that no one ever reads.
LOCKFILE_NAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "npm-shrinkwrap.json",
        "cargo.lock",
        "poetry.lock",
        "pdm.lock",
        "uv.lock",
        "gemfile.lock",
        "composer.lock",
        "go.sum",
        "flake.lock",
    }
)

# A line this long is not written by a person. Minified bundles are one line of
# 300 KB; embedding that produces a vector that means nothing and a citation no
# one can read.
MAX_SOURCE_LINE_LENGTH = 2000
GENERATED_SOURCE_REASON = "The file looks generated or minified and was not indexed."


def is_lockfile(name: str) -> bool:
    return name.lower() in LOCKFILE_NAMES


def is_secret_env_file(name: str) -> bool:
    """True for a real ``.env`` (secrets), False for ``.env.example`` and friends."""
    lowered = name.lower()
    if not lowered.startswith(".env"):
        return False
    return not lowered.endswith(ENV_TEMPLATE_SUFFIXES)


def is_env_template(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(".env") and lowered.endswith(ENV_TEMPLATE_SUFFIXES)


def is_build_output(relative_path: str) -> bool:
    """Bundled/compiled output: minified files, source maps, and anything under a
    dist/build/out directory. .gitignore usually hides these — usually is not a
    guarantee, and one committed bundle can outweigh the whole real codebase."""
    path = PurePosixPath(relative_path)
    name = path.name.lower()
    if name.endswith((".min.js", ".min.css", ".map", ".bundle.js")):
        return True
    return any(part.lower() in {"dist", "build", "out", "vendor"} for part in path.parts[:-1])


def is_generated_source(content: str) -> bool:
    """Content-level check for a file that survived the name checks: one absurdly
    long line is the signature of a minified bundle or a generated blob."""
    return any(len(line) > MAX_SOURCE_LINE_LENGTH for line in content.splitlines())


def source_language(extension: str | None) -> str | None:
    return SOURCE_CODE_LANGUAGES.get((extension or "").lower())


def dominant_source_language(paths: list[str]) -> tuple[str | None, int]:
    """The language most of the source files are written in, and how many files
    that is. Used so a TypeScript repo introduces itself as one instead of as
    'unknown'. Ties are broken alphabetically, so the answer is deterministic."""
    counts: dict[str, int] = {}
    for path in paths:
        language = source_language(PurePosixPath(path).suffix)
        if language:
            counts[language] = counts.get(language, 0) + 1
    if not counts:
        return None, 0
    language = sorted(counts, key=lambda name: (-counts[name], name))[0]
    return language, counts[language]
