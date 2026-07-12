"""What a tester needs to know before touching a strange repository.

Where the tests are, what runs them, how to run them yourself, and — the question
nobody wants to answer out loud — what has no tests at all. All of it is written in
the files; none of it needs a model.

The honesty rule that matters here: **we do not report coverage.** Coverage is a
number produced by running the tests, and we do not run anything. What we can say
truthfully is which modules have a test file that names them and which do not. That
is a weaker claim, and it is stated as such — "no test file mentions this", not
"this is untested".

Pure: no I/O, no state.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# A file is a test because of where it lives or what it is called — the two
# conventions every ecosystem agrees on.
_TEST_PATH_RE = re.compile(
    r"(^|/)(tests?|spec|specs|__tests__|e2e|integration[_-]tests?)(/|$)", re.IGNORECASE
)
_TEST_NAME_RE = re.compile(
    r"(^test_.*|.*_test\.[a-z]+$|.*\.test\.[a-z]+$|.*\.spec\.[a-z]+$|.*Test\.java$|.*Tests\.cs$)"
)

# Framework → the import/usage that proves it, and the command that runs it. The
# command is only claimed when we saw the framework; we never invent a "how to run".
_FRAMEWORK_SIGNALS: list[tuple[str, re.Pattern[str], str]] = [
    ("pytest", re.compile(r"\bimport pytest\b|\bfrom pytest\b|@pytest\."), "pytest"),
    ("unittest", re.compile(r"\bimport unittest\b|unittest\.TestCase"), "python -m unittest"),
    ("jest", re.compile(r"\bfrom ['\"]@jest|\bjest\.(fn|mock|spyOn)\b|\bdescribe\("), "npx jest"),
    ("vitest", re.compile(r"from ['\"]vitest['\"]"), "npx vitest run"),
    ("playwright", re.compile(r"from ['\"]@playwright/test['\"]"), "npx playwright test"),
    ("cypress", re.compile(r"\bcy\.(visit|get)\b"), "npx cypress run"),
    ("go test", re.compile(r"func Test\w+\(t \*testing\.T\)"), "go test ./..."),
    ("junit", re.compile(r"org\.junit"), "mvn test"),
    ("rspec", re.compile(r"\bRSpec\.describe\b"), "bundle exec rspec"),
    ("cargo test", re.compile(r"#\[cfg\(test\)\]|#\[test\]"), "cargo test"),
]

# Tests that exist but do not run. Every ecosystem has its own way of saying it.
_SKIP_RE = re.compile(
    r"@pytest\.mark\.skip|@pytest\.mark\.xfail|@unittest\.skip|"
    r"\b(it|test|describe)\.(skip|todo)\b|\bxit\(|\bxdescribe\(|t\.Skip\(|#\[ignore\]",
)

_MAX_FILES = 2000


@dataclass(frozen=True)
class TestSuite:
    """One place tests live, e.g. `backend/tests` or `frontend/src/__tests__`."""

    # pytest collects any class whose name starts with "Test". These are domain
    # types that happen to be *about* tests, not tests themselves.
    __test__ = False

    path: str
    files_count: int
    frameworks: list[str] = field(default_factory=list)
    test_cases: int = 0
    skipped_cases: int = 0


@dataclass(frozen=True)
class TestFacts:
    __test__ = False

    suites: list[TestSuite] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    # How to actually run them, in the project's own words: a CI step, a Makefile
    # target, an npm script — and only then a framework default.
    run_commands: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    skipped_cases: int = 0
    # Modules/dirs of real code that no test file so much as mentions.
    untested_areas: list[str] = field(default_factory=list)
    ci_test_jobs: list[str] = field(default_factory=list)

    @property
    def test_files_count(self) -> int:
        return len(self.test_files)

    @property
    def test_cases(self) -> int:
        return sum(suite.test_cases for suite in self.suites)


def is_test_file(path: str, content: str | None = None) -> bool:
    """Living in a test directory is proof. A test-ish *name* is only a suspicion:
    `test_suites.py` in a source package is production code, and calling it a test
    would put it in the tester's suite list and pretend the project is better tested
    than it is. When we have the content, the file must actually contain a test case
    or a test framework to qualify."""
    posix = PurePosixPath(path)
    if _TEST_PATH_RE.search(str(posix.parent)):
        return True
    if not _TEST_NAME_RE.match(posix.name):
        return False
    if content is None:
        return True
    # A test-shaped *name* outside a test directory has to prove itself by importing
    # a test framework. Counting `def test_…` alone is not enough: production code is
    # full of `def test_connection()`, and calling those tests would inflate the
    # numbers a tester relies on.
    return bool(_frameworks_in(content))


def _suite_root(path: str) -> str:
    """The directory a suite is rooted at — the first tests/spec/__tests__ segment,
    so `backend/tests/unit/test_x.py` and `backend/tests/test_y.py` are one suite."""
    parts = PurePosixPath(path).parts
    for index, part in enumerate(parts):
        if part.lower() in {"tests", "test", "spec", "specs", "__tests__", "e2e"}:
            return "/".join(parts[: index + 1])
    return str(PurePosixPath(path).parent)


def _strip_strings(content: str) -> str:
    """String and comment bodies blanked out.

    Code that *talks about* tests is not a test: a linter with `def test_` inside a
    regex literal, or a docstring quoting a test name, must not be counted as a test
    case — nor make its file look like a test suite.
    """
    content = re.sub(r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'', '""', content)
    content = re.sub(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'', '""', content)
    return re.sub(r"#[^\n]*|//[^\n]*", "", content)


def _count_cases(content: str) -> int:
    """Test cases in one file. Deliberately syntactic — a `def test_x` or an `it(...)`
    — because that is what a reader would count."""
    code = _strip_strings(content)
    return (
        len(re.findall(r"^\s*(?:async\s+)?def test_\w+", code, re.MULTILINE))
        + len(re.findall(r"^\s*(?:it|test)\s*\(", code, re.MULTILINE))
        + len(re.findall(r"^\s*func Test\w+\(", code, re.MULTILINE))
        + len(re.findall(r"^\s*@Test\b", code, re.MULTILINE))
    )


def _frameworks_in(content: str) -> list[str]:
    return [name for name, pattern, _ in _FRAMEWORK_SIGNALS if pattern.search(content)]


def _framework_command(framework: str) -> str | None:
    for name, _, command in _FRAMEWORK_SIGNALS:
        if name == framework:
            return command
    return None


def run_commands_from_project(files: dict[str, str], frameworks: list[str]) -> list[str]:
    """How this project says its tests are run.

    Its own words first — a `test:` target in the Makefile, a `"test"` script in
    package.json — because that is the command that actually works here (right env,
    right flags). The framework default is the fallback, not the headline.
    """
    commands: list[str] = []

    for path, content in files.items():
        name = PurePosixPath(path).name.lower()
        if name in {"makefile", "gnumakefile"}:
            for target in re.findall(r"^([a-zA-Z0-9_.-]*test[a-zA-Z0-9_.-]*):", content, re.M):
                commands.append(f"make {target}")
        elif name == "package.json":
            try:
                scripts = (json.loads(content) or {}).get("scripts") or {}
            except (json.JSONDecodeError, AttributeError):
                continue
            for script in scripts:
                if "test" in script.lower():
                    commands.append(f"npm run {script}")

    for framework in frameworks:
        command = _framework_command(framework)
        if command and command not in commands:
            commands.append(command)

    # Deduplicate, keep first-seen order: the project's own commands stay on top.
    return list(dict.fromkeys(commands))[:6]


def ci_test_jobs(ci_job_names: list[str]) -> list[str]:
    """CI jobs whose name says they test. A tester's first question about a pipeline
    is 'does anything here actually run the tests', and this answers it from the
    pipeline's own job names."""
    return [name for name in ci_job_names if re.search(r"test|spec|e2e|lint|check", name, re.I)]


def untested_areas(
    source_paths: list[str], test_contents: dict[str, str], limit: int = 8
) -> list[str]:
    """Top-level source areas that no test file mentions by name.

    A weak, honest signal: we look for the module's own name inside the test sources.
    It cannot prove something is untested — only that nothing in the tests says its
    name, which is exactly how it is worded to the user.
    """
    haystack = "\n".join(test_contents.values()).lower()
    areas: dict[str, int] = {}
    for path in source_paths:
        parts = PurePosixPath(path).parts
        if len(parts) < 2 or is_test_file(path):
            continue
        # The module directory, e.g. "app/adapters" — not the whole file.
        area = "/".join(parts[:2])
        areas.setdefault(area, 0)
        areas[area] += 1

    missing = []
    for area, count in sorted(areas.items(), key=lambda item: -item[1]):
        leaf = area.rsplit("/", 1)[-1].lower()
        if len(leaf) < 3:
            continue
        if leaf not in haystack:
            missing.append(area)
    return missing[:limit]


def build_test_facts(
    files: dict[str, str],
    source_paths: list[str],
    ci_job_names: list[str] | None = None,
) -> TestFacts:
    """``files`` is {path: content} for every readable text file we were given."""
    test_files = sorted(
        path for path in list(files)[:_MAX_FILES] if is_test_file(path, files[path])
    )
    test_contents = {path: files[path] for path in test_files}

    suites: dict[str, list[str]] = {}
    for path in test_files:
        suites.setdefault(_suite_root(path), []).append(path)

    all_frameworks: list[str] = []
    suite_list: list[TestSuite] = []
    total_skipped = 0

    for root, paths in sorted(suites.items()):
        frameworks: list[str] = []
        cases = 0
        skipped = 0
        for path in paths:
            content = files[path]
            cases += _count_cases(content)
            skipped += len(_SKIP_RE.findall(content))
            for framework in _frameworks_in(content):
                if framework not in frameworks:
                    frameworks.append(framework)
        total_skipped += skipped
        suite_list.append(
            TestSuite(
                path=root,
                files_count=len(paths),
                frameworks=frameworks,
                test_cases=cases,
                skipped_cases=skipped,
            )
        )
        for framework in frameworks:
            if framework not in all_frameworks:
                all_frameworks.append(framework)

    return TestFacts(
        suites=suite_list,
        frameworks=all_frameworks,
        run_commands=run_commands_from_project(files, all_frameworks),
        test_files=test_files,
        skipped_cases=total_skipped,
        untested_areas=untested_areas(source_paths, test_contents),
        ci_test_jobs=ci_test_jobs(ci_job_names or []),
    )
