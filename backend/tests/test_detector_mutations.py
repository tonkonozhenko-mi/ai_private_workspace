"""Mutation testing for the fabrication detector: robust, not merely tuned.

The detector was corrected three times in one week, each time because it
accused an honest answer (bracket truncation, the prompt's own example, the
model's inline draft). Every correction shipped with a hand-picked
still-catches-real-inventions test — and a hand-picked set is exactly what a
detector can end up tuned TO. This suite generates its adversaries instead:
take a grounded answer citing a real page, mutate the citation into a
plausible fabrication (typo, plural, wrong extension, phantom version, a file
from a different corpus), and require the detector to catch every one while
still passing every unmutated original.

Two numbers, asserted together, form the release gate: fabrication recall
must stay at 100% over the generated classes, and the false-positive rate on
grounded citations must stay at 0%. A change that improves one at the
expense of the other fails here, loudly.

Deliberately NOT a mutation class: moving a file to a different directory
while keeping its basename. The detector accepts basename matches by design
("citing `backend.tf` for `infra/backend.tf` is fine"), so that leniency is
documented rather than tested against.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.domain.rag_answer_evaluator import (
    CITATION_EXAMPLE_PATH,
    find_unsupported_citations,
)
from eval.make_wiki_corpus import generate


@pytest.fixture(scope="module")
def corpus(tmp_path_factory) -> dict[str, str]:
    """Every markdown page of the deterministic wiki corpus: rel path -> text."""
    root = generate(tmp_path_factory.mktemp("wiki") / "corpus")
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in root.rglob("*.md")
        if p.is_file()
    }


def _mutants(path: str) -> list[str]:
    """Plausible fabrications derived from a real path — the shapes a model
    actually produces when it misremembers: a typo, a plural, the wrong
    extension, a version that never existed, and a file from another corpus
    entirely."""
    stem, ext = path.rsplit(".", 1)
    return [
        stem[:-2] + "x" + stem[-2:] + "." + ext,  # typo inside the stem
        stem + "s." + ext,                        # pluralised
        stem + ".txt",                            # wrong extension
        stem + "_v9." + ext,                      # phantom version
        "infra/prod/main.tf",                     # another corpus's file
    ]


def _grounded_answers(path: str) -> list[str]:
    # Both forms the detector reads: backticked (what the prompt asks for) and
    # plain prose (what a model writes when it is not obeying).
    return [
        f"The decision is recorded in `{path}`.",
        f"The decision is recorded in {path}.",
    ]


def test_zero_false_positives_on_grounded_citations(corpus):
    flagged = []
    for path, content in corpus.items():
        for answer in _grounded_answers(path):
            bad = find_unsupported_citations(answer, [path], [content])
            if bad:
                flagged.append((path, bad))
    assert flagged == [], f"grounded citations accused: {flagged}"


def test_full_recall_on_mutated_citations(corpus):
    all_paths = set(corpus)
    evidence_blob = "\n".join(corpus.values()).casefold()
    missed = []
    total = 0
    for path, content in corpus.items():
        for mutant in _mutants(path):
            # A valid mutant must be a real fabrication: not an existing page,
            # not mentioned anywhere in the evidence, and not rescued by the
            # designed basename/suffix leniencies.
            base = mutant.split("/")[-1].casefold()
            if mutant in all_paths or base in evidence_blob:
                continue
            if any(p.casefold().endswith(base) for p in all_paths):
                continue
            for answer in (
                f"The decision is recorded in `{mutant}`.",
                f"The decision is recorded in {mutant}.",
                # mixed answer: one honest citation, one fabricated — the
                # fabrication must be caught even next to a valid neighbour
                f"See `{path}` and also `{mutant}`.",
            ):
                total += 1
                bad = find_unsupported_citations(answer, [path], [content])
                if mutant not in bad:
                    missed.append((answer, bad))
    recall = 1 - len(missed) / total
    assert not missed, f"recall {recall:.1%} — missed fabrications: {missed[:5]}"
    assert total >= 100, f"mutation space unexpectedly small ({total} cases)"


def test_the_prompts_example_is_immune_but_its_mutants_are_not(corpus):
    path, content = next(iter(corpus.items()))
    # The placeholder itself: read, not invented.
    assert find_unsupported_citations(f"Cite like `{CITATION_EXAMPLE_PATH}`.", [path], [content]) == []
    # A near-placeholder is NOT covered by the exemption — it is a fabrication.
    near = CITATION_EXAMPLE_PATH.replace("file", "config")
    bad = find_unsupported_citations(f"The value is set in `{near}`.", [path], [content])
    assert near in bad
