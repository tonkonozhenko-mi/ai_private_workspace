"""Optional .gitignore awareness for project scanning.

The scanner's primary filter is the user-controlled include/exclude pattern
list. On top of that, when enabled, we also honor the project's own
``.gitignore`` files so the local RAG index sees the same files a developer
would commit to git — virtualenvs, ``node_modules``, build output, caches, and
local ``.env`` secrets are skipped automatically.

When the optional ``pathspec`` dependency is installed it is used for fully
git-accurate matching. Otherwise a small built-in matcher covers the common
patterns (directory ignores, ``**`` globs, extensions, anchoring, negation) so
the feature still works in minimal runtimes. The layer is best-effort and never
raises.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

try:  # pragma: no cover - import guard
    from pathspec import GitIgnoreSpec as _PathspecSpec

    _PATHSPEC_AVAILABLE = True
except Exception:  # pragma: no cover - defensive fallback
    _PathspecSpec = None  # type: ignore[assignment]
    _PATHSPEC_AVAILABLE = False


GITIGNORE_FILENAME = ".gitignore"


def _posix(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def discover_gitignore_relative_paths(file_paths: list[str]) -> list[str]:
    """Return relative paths of every ``.gitignore`` among discovered files."""

    found: list[str] = []
    for raw in file_paths:
        normalized = _posix(raw)
        if normalized == GITIGNORE_FILENAME or normalized.endswith("/" + GITIGNORE_FILENAME):
            if normalized not in found:
                found.append(normalized)
    return found


def _translate_line(line: str) -> tuple[re.Pattern[str], bool] | None:
    """Translate one .gitignore line into ``(compiled_regex, negate)``.

    Returns ``None`` for blank lines and comments.
    """

    raw = line.rstrip("\n").rstrip("\r")
    # Trailing whitespace is insignificant unless escaped; keep it simple.
    stripped = raw.strip()
    if not stripped or stripped.startswith("#"):
        return None

    negate = stripped.startswith("!")
    if negate:
        stripped = stripped[1:]

    dir_only = stripped.endswith("/")
    pattern = stripped.rstrip("/")
    pattern = pattern.replace("\\ ", " ")

    anchored = pattern.startswith("/") or ("/" in pattern)
    pattern = pattern.lstrip("/")
    if not pattern:
        return None

    regex = []
    i = 0
    n = len(pattern)
    while i < n:
        char = pattern[i]
        if char == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                # consume the second star
                i += 1
                if i + 1 < n and pattern[i + 1] == "/":
                    regex.append("(?:.*/)?")
                    i += 1
                else:
                    regex.append(".*")
            else:
                regex.append("[^/]*")
        elif char == "?":
            regex.append("[^/]")
        else:
            regex.append(re.escape(char))
        i += 1

    body = "".join(regex)
    prefix = "^" if anchored else "^(?:.*/)?"
    suffix = "/.*$" if dir_only else "(?:/.*)?$"
    return re.compile(prefix + body + suffix), negate


class _FallbackGitIgnoreSpec:
    """Minimal stand-in for ``pathspec.GitIgnoreSpec`` covering common cases."""

    def __init__(self, rules: list[tuple[re.Pattern[str], bool]]) -> None:
        self._rules = rules

    @classmethod
    def from_lines(cls, lines: list[str]) -> _FallbackGitIgnoreSpec:
        rules: list[tuple[re.Pattern[str], bool]] = []
        for line in lines:
            translated = _translate_line(line)
            if translated is not None:
                rules.append(translated)
        return cls(rules)

    def match_file(self, path: str) -> bool:
        matched = False
        for regex, negate in self._rules:
            if regex.match(path):
                matched = not negate
        return matched


def _build_spec(content: str) -> object | None:
    lines = content.splitlines()
    if _PATHSPEC_AVAILABLE:
        try:
            return _PathspecSpec.from_lines(lines)
        except Exception:  # pragma: no cover - defensive
            return None
    try:
        return _FallbackGitIgnoreSpec.from_lines(lines)
    except Exception:  # pragma: no cover - defensive
        return None


@dataclass(frozen=True)
class _ScopedSpec:
    base_dir: str  # "" for the project root, else "sub/dir/"
    spec: object


class GitignoreMatcher:
    """Matches project-relative paths against one or more ``.gitignore`` files."""

    def __init__(self, scoped_specs: list[_ScopedSpec]) -> None:
        self._scoped_specs = scoped_specs

    @property
    def active(self) -> bool:
        return bool(self._scoped_specs)

    @classmethod
    def empty(cls) -> GitignoreMatcher:
        return cls([])

    @classmethod
    def from_sources(cls, sources: dict[str, str]) -> GitignoreMatcher:
        """Build a matcher from ``{gitignore_relative_path: content}``.

        Each ``.gitignore`` is scoped to its own directory, matching git's
        per-directory semantics.
        """

        scoped: list[_ScopedSpec] = []
        for relative_path, content in sources.items():
            if not content:
                continue
            normalized = _posix(relative_path)
            base_dir = ""
            if normalized.endswith(GITIGNORE_FILENAME):
                base_dir = normalized[: -len(GITIGNORE_FILENAME)]
            base_dir = base_dir.lstrip("/")
            spec = _build_spec(content)
            if spec is None:
                continue
            scoped.append(_ScopedSpec(base_dir=base_dir, spec=spec))
        return cls(scoped)

    def is_ignored(self, path: str) -> bool:
        if not self._scoped_specs:
            return False
        normalized = _posix(path)
        for scoped in self._scoped_specs:
            base = scoped.base_dir
            if base:
                if not normalized.startswith(base):
                    continue
                relative = normalized[len(base) :]
            else:
                relative = normalized
            if not relative:
                continue
            try:
                if scoped.spec.match_file(relative):  # type: ignore[attr-defined]
                    return True
            except Exception:  # pragma: no cover - defensive
                continue
        return False
