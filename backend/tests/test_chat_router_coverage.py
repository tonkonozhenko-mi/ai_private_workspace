"""A question about a share price is not a question about the code.

The corpus that exposed this was written by Google, so the word "Google" sits in
every copyright header, and "What is Google's stock price today?" scored 0.590
against a bar of 0.589 — one thousandth above. No threshold can separate those,
and none should have to: the question is chit-chat whatever it scores, and the
router is the layer that knows it. Chasing the 0.001 with a margin would have
been fitting the formula to the benchmark.

The invariant that matters is the second test: not one project question, in any
of the six labelled sets, may be routed away from retrieval. A false positive
here answers a real question ungrounded, which is the failure we care about most.
"""

from app.core.domain.question_intent import looks_general_chat, looks_project_specific
from eval.golden_set import CLASS_SHOULD_ABSTAIN, golden_set
from eval.golden_set_acme import golden_set_acme
from eval.golden_set_external import (
    golden_set_boutique,
    golden_set_fastapi_tmpl,
    golden_set_tf_vpc,
)
from eval.golden_set_wiki import golden_set_wiki

# The questions are read from the pre-registered sets, never re-typed here: a
# router tested against a copy of the benchmark is a router tested against itself.
ALL_SETS = {
    "app": golden_set(),
    "acme": golden_set_acme(),
    "boutique": golden_set_boutique(),
    "fastapi-template": golden_set_fastapi_tmpl(),
    "tf-aws-vpc": golden_set_tf_vpc(),
    "wiki-export": golden_set_wiki(),
}


def test_every_small_talk_question_is_routed_to_general_chat():
    # Should-abstain now has two subclasses with OPPOSITE routing expectations,
    # told apart by id convention. "-sa-" is small talk (borscht, jokes, stock
    # prices): the router must catch it before retrieval. "-adv-" is adversarial
    # (a project-flavoured question the corpus cannot answer — absent tech, a
    # chimera of real entities): routing it to general chat would hand it to the
    # model's imagination, which is the exact failure it exists to probe. It must
    # REACH retrieval and abstain at the threshold.
    missed = [
        (name, case.id, case.question)
        for name, cases in ALL_SETS.items()
        for case in cases
        if case.cls == CLASS_SHOULD_ABSTAIN
        and "-adv-" not in case.id
        and not looks_general_chat(case.question)
    ]
    assert missed == []


def test_adversarial_abstain_questions_are_never_routed_away_from_retrieval():
    routed = [
        (name, case.id, case.question)
        for name, cases in ALL_SETS.items()
        for case in cases
        if case.cls == CLASS_SHOULD_ABSTAIN
        and "-adv-" in case.id
        and looks_general_chat(case.question)
    ]
    assert routed == []


def test_no_project_question_is_ever_routed_away_from_retrieval():
    """The one that would hurt: a project question sent to general chat is answered
    from the model's imagination instead of from the person's files."""
    routed = [
        (name, case.id, case.question)
        for name, cases in ALL_SETS.items()
        for case in cases
        if case.cls != CLASS_SHOULD_ABSTAIN and looks_general_chat(case.question)
    ]
    assert routed == []


def test_a_poem_about_the_project_is_still_about_the_project():
    assert looks_project_specific("Write a poem about this repository")
    assert not looks_general_chat("Write a poem about this repository")
    assert not looks_general_chat("Recommend a good book about this codebase")


def test_the_new_categories_route_on_their_own_terms():
    assert looks_general_chat("Write me a short poem about autumn.")
    assert looks_general_chat("What is Google's stock price today?")
    assert looks_general_chat("Thanks, that's all for now!")
    assert looks_general_chat("Recommend me a good sci-fi movie.")
