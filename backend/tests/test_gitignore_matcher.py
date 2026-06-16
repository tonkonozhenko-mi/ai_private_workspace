from app.core.domain.gitignore_matcher import (
    GitignoreMatcher,
    discover_gitignore_relative_paths,
)


SAMPLE_GITIGNORE = """
# Local runtime data
backend/.ai-workbench/
*.db

# Python / frontend build artifacts (match at any depth)
**/.venv/
**/__pycache__/
*.pyc
**/node_modules/
frontend/dist/

# Virtual environments and caches
.venv/
backend/.venv-x86_64/

# Local environment files
.env
**/.env
!*.env.example

build/
"""


def _matcher() -> GitignoreMatcher:
    return GitignoreMatcher.from_sources({".gitignore": SAMPLE_GITIGNORE})


def test_discover_gitignore_paths():
    files = [
        "README.md",
        ".gitignore",
        "frontend/.gitignore",
        "backend/app/main.py",
    ]
    assert discover_gitignore_relative_paths(files) == [
        ".gitignore",
        "frontend/.gitignore",
    ]


def test_nested_virtualenv_is_ignored():
    matcher = _matcher()
    assert matcher.is_ignored(
        "backend/.venv-x86_64/lib/python3.9/site-packages/pip/_internal/x.py"
    )
    assert matcher.is_ignored("backend/.venv/lib/python3.11/site-packages/x.py")
    assert matcher.is_ignored("frontend/node_modules/react/index.js")


def test_caches_and_artifacts_are_ignored():
    matcher = _matcher()
    assert matcher.is_ignored("backend/app/__pycache__/main.pyc")
    assert matcher.is_ignored("module.pyc")
    assert matcher.is_ignored("frontend/dist/index.js")
    assert matcher.is_ignored("build/desktop/app")
    assert matcher.is_ignored("backend/.ai-workbench/store.db")


def test_env_files_ignored_but_example_kept():
    matcher = _matcher()
    assert matcher.is_ignored("backend/.env")
    assert matcher.is_ignored(".env")
    assert not matcher.is_ignored("config.env.example")


def test_source_files_are_not_ignored():
    matcher = _matcher()
    assert not matcher.is_ignored("backend/app/core/use_cases/scan_project.py")
    assert not matcher.is_ignored("README.md")
    assert not matcher.is_ignored("frontend/src/components/ProjectUnderstanding.tsx")
    assert not matcher.is_ignored("docs/ARCHITECTURE.md")


def test_empty_matcher_ignores_nothing():
    matcher = GitignoreMatcher.empty()
    assert not matcher.active
    assert not matcher.is_ignored("backend/.venv/x.py")


def test_nested_gitignore_is_scoped_to_its_directory():
    matcher = GitignoreMatcher.from_sources(
        {"frontend/.gitignore": "generated/\n"}
    )
    assert matcher.is_ignored("frontend/generated/bundle.js")
    # The same folder name outside the nested gitignore's directory is untouched.
    assert not matcher.is_ignored("backend/generated/bundle.js")
