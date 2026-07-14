"""The external benchmark's deterministic guarantees, pinned in CI.

The scored runs need local models and hours; these tests need neither. What CI
pins instead is everything that makes the published numbers trustworthy:
commits are really pinned, the generated wiki corpus cannot drift under its
pre-registered questions, question ids never collide, and every wiki label
points at a page the generator actually writes.
"""

from __future__ import annotations

import re
from pathlib import Path

from eval.corpora import CORPORA
from eval.golden_set import CLASS_PROJECT_PRECISE, golden_set
from eval.golden_set_acme import golden_set_acme
from eval.golden_set_external import (
    golden_set_boutique,
    golden_set_fastapi_tmpl,
    golden_set_tf_vpc,
)
from eval.golden_set_wiki import golden_set_wiki
from eval.make_wiki_corpus import content_hash, generate

ALL_SETS = {
    "app": golden_set,
    "acme": golden_set_acme,
    "tf-aws-vpc": golden_set_tf_vpc,
    "online-boutique": golden_set_boutique,
    "fastapi-template": golden_set_fastapi_tmpl,
    "wiki-export": golden_set_wiki,
}

# The pre-registered wiki corpus, frozen. If this hash moves, the corpus moved
# under its questions — that must be a deliberate commit that re-registers the
# set, never a side effect.
WIKI_CORPUS_HASH = "b9b570b7b5de6dbe"


def test_git_corpora_are_pinned_to_full_shas():
    for corpus in CORPORA.values():
        if corpus.git_url:
            assert re.fullmatch(r"[0-9a-f]{40}", corpus.commit), corpus.name
            assert corpus.git_url.startswith("https://github.com/"), corpus.name


def test_every_external_set_has_a_corpus():
    from eval.golden import EXTERNAL_SETS

    assert set(EXTERNAL_SETS) <= set(CORPORA)


def test_question_ids_are_unique_across_all_sets():
    seen: set[str] = set()
    for name, fn in ALL_SETS.items():
        for case in fn():
            assert case.id not in seen, f"duplicate question id {case.id} ({name})"
            seen.add(case.id)


def test_precise_questions_always_name_their_answer_files():
    for name, fn in ALL_SETS.items():
        for case in fn():
            if case.cls == CLASS_PROJECT_PRECISE:
                assert case.expected_paths, f"{case.id} ({name}) has no expected_paths"


def test_wiki_corpus_is_deterministic_and_pinned(tmp_path: Path):
    root_a = generate(tmp_path / "a")
    root_b = generate(tmp_path / "b")
    files_a = {
        p.relative_to(root_a).as_posix(): p.read_bytes() for p in root_a.rglob("*") if p.is_file()
    }
    files_b = {
        p.relative_to(root_b).as_posix(): p.read_bytes() for p in root_b.rglob("*") if p.is_file()
    }
    assert files_a == files_b
    assert content_hash() == WIKI_CORPUS_HASH


def test_wiki_labels_point_at_generated_pages(tmp_path: Path):
    root = generate(tmp_path / "corpus")
    generated = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    for case in golden_set_wiki():
        for expected in case.expected_paths:
            assert any(path.endswith(expected) for path in generated), (
                f"{case.id}: no generated page matches {expected!r}"
            )


def test_acme_new_labels_exist_on_disk():
    demo = Path(__file__).resolve().parents[2] / "build" / "demo-project"
    for case in golden_set_acme():
        for expected in case.expected_paths:
            assert any(demo.glob(f"**/{Path(expected).name}")), (
                f"{case.id}: {expected} not found under build/demo-project"
            )
