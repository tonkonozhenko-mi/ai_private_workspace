"""Deterministic domain-synonym expansion for retrieval (P7b)."""

from app.core.domain.query_synonyms import expand_query_synonyms, synonym_additions


def test_csp_question_gains_the_file_spelling():
    # The pp-csp golden case: question says "Content-Security-Policy", the file
    # (tauri.conf.json) uses the key "csp". Expansion bridges the gap.
    adds = synonym_additions("What Content-Security-Policy does the desktop app set?")
    assert "csp" in adds


def test_abbreviation_expands_to_full_form():
    assert "kubernetes" in synonym_additions("How does k8s deploy?")
    assert "terraform" in synonym_additions("what does the tf module do")


def test_full_form_expands_to_abbreviation():
    assert "content-security-policy" in synonym_additions("what is the csp setting")
    assert "k8s" in synonym_additions("our kubernetes cluster")


def test_symmetric_and_deduplicated():
    # When both forms are already present, nothing is added.
    assert synonym_additions("csp content-security-policy content security policy") == []


def test_no_match_leaves_query_unchanged():
    q = "How does MMR pick a diverse subset of chunks?"
    assert synonym_additions(q) == []
    assert expand_query_synonyms(q) == q


def test_expand_appends_without_reordering():
    q = "the csp header"
    out = expand_query_synonyms(q)
    assert out.startswith(q)  # original wording preserved up front
    assert "content-security-policy" in out


def test_word_boundaries_avoid_false_positives():
    # "prod" is a synonym of "production", but must not fire inside "product".
    assert "production" not in synonym_additions("what does the product roadmap say")
    # "ci" must not fire inside "special".
    assert "continuous integration" not in synonym_additions("this is a special case")
