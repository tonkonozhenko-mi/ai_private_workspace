"""Deterministic guard rails for the external (ACME) golden set, runnable in CI
without an embedder or an LLM.

The retrieval eval needs Ollama and minutes to run, so a mislabelled question — one
whose ``expected_paths`` point at a file that no longer exists in the demo repo, or
a should-abstain question the router doesn't actually route away — would only
surface on a manual run, if ever. These pure checks pin the set in seconds:

- every ``expected_paths`` entry refers to a real file under ``build/demo-project``,
  so the labels can't silently rot as the demo repo evolves;
- every should-abstain question routes to general chat and no project question
  does (same router contract the app set is held to);
- ids are unique and every precise question actually carries a label.
"""

from pathlib import Path

from app.core.domain.question_intent import looks_general_chat
from eval.golden_set import (
    CLASS_PROJECT_BROAD,
    CLASS_PROJECT_PRECISE,
    CLASS_SHOULD_ABSTAIN,
)
from eval.golden_set_acme import ACME_REPO_RELATIVE, golden_set_acme

_PROJECT_CLASSES = (CLASS_PROJECT_PRECISE, CLASS_PROJECT_BROAD)


def _demo_repo() -> Path:
    # backend/tests/ -> backend -> repo root -> build/demo-project
    return Path(__file__).resolve().parents[2] / ACME_REPO_RELATIVE


def test_demo_repo_is_present():
    repo = _demo_repo()
    assert repo.is_dir(), f"ACME demo repo missing at {repo}"


def test_every_expected_path_points_at_a_real_file():
    repo = _demo_repo()
    existing = {p.relative_to(repo).as_posix() for p in repo.rglob("*") if p.is_file()}
    missing = []
    for case in golden_set_acme():
        for label in case.expected_paths:
            # expected_paths are matched as suffixes/substrings against retrieved
            # paths, so a label is valid iff some real file path contains it.
            if not any(label in path for path in existing):
                missing.append((case.id, label))
    assert not missing, f"labels not backed by a real file in the demo repo: {missing}"


def test_precise_questions_carry_labels_others_do_not():
    for case in golden_set_acme():
        if case.cls == CLASS_PROJECT_PRECISE:
            assert case.expected_paths, f"{case.id} is project_precise but has no expected_paths"
        else:
            assert not case.expected_paths, f"{case.id} is {case.cls} but carries expected_paths"


def test_every_should_abstain_question_routes_to_general_chat():
    misses = [
        c.id
        for c in golden_set_acme()
        if c.cls == CLASS_SHOULD_ABSTAIN and not looks_general_chat(c.question)
    ]
    assert not misses, f"should-abstain questions NOT routed to general chat: {misses}"


def test_no_project_question_is_routed_to_general_chat():
    wrong = [
        c.id
        for c in golden_set_acme()
        if c.cls in _PROJECT_CLASSES and looks_general_chat(c.question)
    ]
    assert not wrong, f"project questions wrongly routed to general chat: {wrong}"


def test_ids_are_unique_and_questions_non_empty():
    cases = golden_set_acme()
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "duplicate question ids in the ACME golden set"
    assert all(c.question.strip() for c in cases), "a question is empty"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
