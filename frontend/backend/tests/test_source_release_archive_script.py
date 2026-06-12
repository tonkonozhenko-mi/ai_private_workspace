from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_source_release_archive_script_exists_and_mentions_required_excludes() -> None:
    script = PROJECT_ROOT / "scripts" / "prepare_source_release_archive.sh"

    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "audit_release_candidate.sh" in text
    assert "backend/.ai-workbench" in text
    assert "*.sqlite3" in text
    assert "backend/.venv" in text
    assert "*.tsbuildinfo" in text
    assert "build/release" in text


def test_github_repository_files_exist() -> None:
    expected = [
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".github/workflows/ci.yml",
        ".github/workflows/desktop-packaging-checks.yml",
        ".github/pull_request_template.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        "docs/assets/product-flow.svg",
        "docs/V1_PRODUCT_COMPLETION_ROADMAP.md",
        "docs/GITHUB_PUBLICATION_CHECKLIST.md",
    ]

    for relative_path in expected:
        assert (PROJECT_ROOT / relative_path).exists(), f"Missing {relative_path}"
