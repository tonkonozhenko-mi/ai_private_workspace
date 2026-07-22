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
    # The Microsoft/JVM/BEAM half of the world, which the first pass of this
    # dictionary missed entirely. An Azure shop's infrastructure is .bicep and its
    # automation is .ps1 — exactly the two files a DevOps question is about, and
    # both were landing as "unknown" and going unindexed without saying so.
    ".bicep": "Bicep",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell",
    ".groovy": "Groovy",
    ".vb": "Visual Basic",
    ".fs": "F#",
    ".fsx": "F#",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".proto": "Protobuf",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
}

SOURCE_CODE_EXTENSIONS = frozenset(SOURCE_CODE_LANGUAGES)

# Config formats that aren't YAML or JSON. pyproject.toml, setup.cfg, my.ini and
# friends answer "how is X configured" — the single most common question about a
# repository after "where is X".
CONFIG_EXTENSIONS = frozenset(
    {
        ".toml",
        ".ini",
        ".cfg",
        ".properties",
        ".conf",
        ".editorconfig",
        # A .sln is a solution manifest in a format of its own — not XML — and it
        # is the one file that says which projects a .NET repository contains.
        ".sln",
    }
)

# XML that is a build or project definition rather than a document. A .csproj is
# where a .NET project lists its dependencies and target framework: the answer to
# "what does this service depend on", previously unread because the type rule
# asked for the literal extension ".xml".
XML_CONFIG_EXTENSIONS = frozenset({".xml", ".csproj", ".vbproj", ".fsproj", ".props", ".targets"})

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


# What the operating system leaves behind in every folder it has ever displayed.
# .DS_Store is not a config file, it is Finder's memory of the icon positions — and
# it was being counted, listed and offered to the person as part of their project.
_OS_CLUTTER = frozenset(
    {".ds_store", "thumbs.db", "desktop.ini", ".localized", "icon\r", ".spotlight-v100"}
)


def is_os_clutter(name: str) -> bool:
    return name.lower() in _OS_CLUTTER


def is_build_output(relative_path: str) -> bool:
    """Bundled/compiled output: minified files, source maps, and anything under a
    dist/build/out directory. .gitignore usually hides these — usually is not a
    guarantee, and one committed bundle can outweigh the whole real codebase."""
    path = PurePosixPath(relative_path)
    name = path.name.lower()
    if name.endswith((".min.js", ".min.css", ".map", ".bundle.js")):
        return True
    return any(part.lower() in {"dist", "build", "out", "vendor"} for part in path.parts[:-1])


# The line a code generator writes at the top of its output, in the language of
# whoever wrote the generator. Machine-written code answers questions about the
# machine, not about the project: asked where the gRPC API is defined, a repo of
# Go services answered with three protobuf stubs instead of the .proto file a
# person actually wrote.
_GENERATED_MARKERS = (
    "code generated",
    "do not edit",
    "@generated",
    "autogenerated",
    "auto-generated",
)
# Comment openers across the languages we index. The marker must be *in a comment*
# — prose in a README saying "do not edit this section" is not a generator's
# signature — and in the header, not somewhere in the middle of the file.
_COMMENT_OPENERS = ("//", "#", "/*", "*", "--", "<!--", ";")
# The header is the leading run of comment/blank lines, NOT a fixed number of
# lines: Google's genproto stubs carry a 14-line Apache licence above the
# "Code generated" stamp (line 15 — observed on online-boutique, 2026-07-14,
# where a 10-line window missed all 8 stubs). The cap only bounds the scan on
# degenerate files that are one huge comment.
_GENERATED_HEADER_SCAN_LINES = 100


# Every detected_type a generator's stamp can appear in — not just SOURCE_CODE.
# Found live on online-boutique (2026-07-14): the Go stubs fell to the filter but
# src/emailservice/demo_pb2_grpc.py sailed through, because .py is detected as
# "python", the filter fired only for SOURCE_CODE, and a Python protobuf stub
# took a top-5 slot for "Where is the gRPC API defined?". Same stamp culture
# elsewhere: Terragrunt writes "# Generated by Terragrunt" into .tf files.
#
# The languages added later — PowerShell, Bicep and the rest — need no entry here:
# they are detected as SOURCE_CODE, which is already the first member of this set.
# Both stamp their output in a comment we recognise (`#` for PowerShell, `//` for
# Bicep), so a generated .ps1 is filtered by the rule that was already here.
GENERATED_CHECKED_TYPES = frozenset({SOURCE_CODE, SQL, "python", "shell", "terraform"})


def _is_generated_marker(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped.startswith(_COMMENT_OPENERS):
        return False
    lowered = stripped.lower()
    return any(marker in lowered for marker in _GENERATED_MARKERS)


def _header_comment_lines(lines: list[str]):
    """The file's leading comment block: consecutive comment or blank lines from
    the top, ending at the first line of actual code. A marker below that point
    is quotation, not a generator's signature."""
    for line in lines[:_GENERATED_HEADER_SCAN_LINES]:
        stripped = line.lstrip()
        if not stripped:
            continue  # blank lines separate licence from stamp; still the header
        if not stripped.startswith(_COMMENT_OPENERS):
            return
        yield line


def is_generated_source(content: str) -> bool:
    """Content-level check for a file that survived the name checks.

    Two signatures: one absurdly long line (a minified bundle or a blob), and the
    header a generator stamps on its own output ("// Code generated by
    protoc-gen-go-grpc. DO NOT EDIT."). Both mean the same thing — nobody wrote
    this, so nobody should be pointed at it as an answer.
    """
    lines = content.splitlines()
    if any(len(line) > MAX_SOURCE_LINE_LENGTH for line in lines):
        return True
    return any(_is_generated_marker(line) for line in _header_comment_lines(lines))


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


# Pictures. We cannot read them without OCR, and we will not pretend otherwise —
# but a project's diagrams and screenshots are worth *knowing about*, so they are
# detected, attributed to the document they belong to, and honestly left unindexed.
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".svg"}
)
