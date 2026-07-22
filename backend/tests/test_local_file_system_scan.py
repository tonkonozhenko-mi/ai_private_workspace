"""The project file walk must skip heavy vendored/VCS directories WITHOUT
descending into them (that walk of a whole monorepo/.git was the slow scan)."""

import tempfile
from pathlib import Path

from app.adapters.filesystem.local_file_system import LocalFileSystem


def _touch(root: Path, rel: str, text: str = "x") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_scan_excludes_skipped_directories():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        # Real project files.
        _touch(root, "main.py", "print()\n")
        _touch(root, "src/app.py", "x")
        _touch(root, "README.md", "# hi")
        # Heavy directories that must be pruned, not walked.
        _touch(root, ".git/objects/pack/huge", "junk")
        _touch(root, "node_modules/left-pad/index.js", "module.exports")
        _touch(root, ".venv/lib/site.py", "junk")
        _touch(root, "target/debug/app", "binary")

        result = LocalFileSystem().list_files(str(root))
        paths = {f.path for f in result}

        assert paths == {"main.py", "src/app.py", "README.md"}
        # Nothing from a skipped tree leaked in.
        assert not any(p.startswith((".git/", "node_modules/", ".venv/", "target/")) for p in paths)


def test_scan_does_not_descend_into_a_symlink_loop_in_a_skipped_dir():
    # If the walk descended into node_modules it could follow a self-referential
    # symlink and hang/raise. Pruning means it never enters, so this returns fast.
    import os

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _touch(root, "main.py", "print()\n")
        (root / "node_modules").mkdir()
        try:
            os.symlink(str(root / "node_modules"), str(root / "node_modules" / "loop"))
        except (OSError, NotImplementedError):
            return  # platform without symlink support — skip
        result = LocalFileSystem().list_files(str(root))
        assert {f.path for f in result} == {"main.py"}


def test_scan_prunes_gitignored_directories_during_the_walk():
    # A large ignored tree must never be descended into: the .gitignore rule prunes
    # it at the directory level, so its files are not even discovered.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _touch(root, ".gitignore", "big_data/\ncoverage/\n*.log\n")
        _touch(root, "main.py", "print()\n")
        _touch(root, "keep/a.py", "x")
        _touch(root, "run.log", "noise")  # file-level ignore, not a dir prune
        for i in range(50):
            _touch(root, f"big_data/f{i}.json", "{}")
            _touch(root, f"coverage/c{i}.html", "<html>")

        paths = {f.path for f in LocalFileSystem().list_files(str(root))}
        # Ignored directories are absent (never walked)…
        assert not any(p.startswith(("big_data/", "coverage/")) for p in paths), paths
        # …while real files and the .gitignore itself are discovered. run.log is a
        # file-level ignore that the scan use-case filter drops later, not here.
        assert {"main.py", "keep/a.py", ".gitignore", "run.log"} == paths, paths


def test_scan_honours_nested_gitignore_and_can_be_disabled():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _touch(root, "keep/a.py", "x")
        _touch(root, "keep/.gitignore", "tmp/\n")
        for i in range(20):
            _touch(root, f"keep/tmp/t{i}.py", "x")

        pruned = {f.path for f in LocalFileSystem().list_files(str(root))}
        assert not any(p.startswith("keep/tmp/") for p in pruned), pruned

        # With gitignore disabled, the walk descends into everything again.
        full = {f.path for f in LocalFileSystem().list_files(str(root), respect_gitignore=False)}
        assert any(p.startswith("keep/tmp/") for p in full)


def test_the_microsoft_and_beam_extensions_are_read_now():
    """The live gap: an Azure repo's infrastructure and automation were the two
    things a DevOps question is about, and both scanned as "unknown"."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _touch(root, "infra/main.bicep", "param location string")
        _touch(root, "scripts/deploy.ps1", "Write-Host 'hi'")
        _touch(root, "scripts/util.psm1", "function Get-Thing {}")
        _touch(root, "Jenkinsfile.groovy", "pipeline {}")
        _touch(root, "src/App.fs", "let x = 1")
        _touch(root, "lib/thing.ex", "defmodule Thing do end")
        _touch(root, "node/thing.erl", "-module(thing).")
        _touch(root, "legacy/Form1.vb", "Public Class Form1")
        # .NET project files: XML that says what a service depends on, and the
        # solution manifest that says which projects exist.
        _touch(root, "src/Api.csproj", '<Project Sdk="Microsoft.NET.Sdk" />')
        _touch(root, "App.sln", "Microsoft Visual Studio Solution File")
        _touch(root, "notes/thing.xyz", "who knows")

        by_path = {f.path: f.detected_type for f in LocalFileSystem().list_files(str(root))}

        for path in (
            "infra/main.bicep",
            "scripts/deploy.ps1",
            "scripts/util.psm1",
            "Jenkinsfile.groovy",
            "src/App.fs",
            "lib/thing.ex",
            "node/thing.erl",
            "legacy/Form1.vb",
        ):
            assert by_path[path] == "source_code", (path, by_path[path])
        assert by_path["src/Api.csproj"] == "xml_config"
        assert by_path["App.sln"] == "config"
        # And the one we still cannot name stays unknown — which is the honest
        # answer, and the thing the Home line now says out loud.
        assert by_path["notes/thing.xyz"] == "unknown"


def test_a_generated_powershell_file_is_still_filtered():
    """Adding a language must not add a way for machine output back into the
    index. PowerShell stamps its generators in a `#` comment, which is the rule
    that was already here; this only proves the new type reaches it."""
    from app.core.domain.source_files import GENERATED_CHECKED_TYPES, is_generated_source

    generated = "# Code generated by AutoRest. DO NOT EDIT.\n\nfunction Get-Thing {}\n"
    handwritten = "# Deploys the API.\n\nfunction Deploy {}\n"

    assert is_generated_source(generated)
    assert not is_generated_source(handwritten)
    # PowerShell and Bicep arrive as source_code, which the filter already checks —
    # no new entry, and the mutation gate is untouched.
    assert "source_code" in GENERATED_CHECKED_TYPES


def test_only_images_are_known_but_unindexable():
    """The blind-spot count treats "unknown" as the whole of what we could not
    read. That is only true while "image" is the sole other type the index
    refuses — if a third appears, this fails and the count must be told."""
    from app.adapters.filesystem.local_file_system import LocalFileSystem as _FS
    from app.core.use_cases.index_workspace import INDEXABLE_FILE_TYPES

    _ = _FS  # imported for symmetry with the module under test
    produced = {
        "gitlab_ci",
        "github_actions",
        "terraform",
        "terragrunt",
        "python",
        "docker",
        "helm",
        "kubernetes",
        "markdown",
        "yaml",
        "json",
        "shell",
        "sql",
        "source_code",
        "config",
        "xml_config",
        "makefile",
        "tabular_data",
        "notebook",
        "word_document",
        "excel_workbook",
        "presentation",
        "pdf_document",
        "diagram",
        "image",
        "html",
        "plain_text",
        "unknown",
    }
    assert produced - set(INDEXABLE_FILE_TYPES) == {"image", "unknown"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
