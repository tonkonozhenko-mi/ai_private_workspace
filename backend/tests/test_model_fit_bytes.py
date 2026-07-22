"""One verdict about "will this run on my machine", reached by two routes.

The guided setup reads model sizes out of our own catalog, where they are
written for people to read ("4.7 GB"). A model found on Hugging Face reports
its size in bytes. Both have to arrive at the same answer, or the same model is
"comfortable" on one screen and "too big" on another and neither can be trusted.

Kept apart from test_guided_model_setup.py deliberately: that file needs FastAPI,
and these are pure.
"""

from app.core.domain.model_fit import (
    FIT_TOO_BIG,
    assess_model_fit,
    assess_model_fit_bytes,
)

GB = 1024**3


def test_the_two_routes_agree_on_every_case_that_matters():
    for size_gb, ram_gb in ((0.3, 8), (4.7, 16), (7.0, 8), (13.0, 16), (13.0, 64)):
        from_label = assess_model_fit(f"{size_gb} GB", float(ram_gb))
        from_bytes = assess_model_fit_bytes(int(size_gb * GB), int(ram_gb * GB))

        assert from_label == from_bytes, (size_gb, ram_gb, from_label, from_bytes)


def test_an_unknown_size_or_machine_gets_no_verdict_at_all():
    """Saying "comfortable" because we failed to measure is the worst of the
    three answers: it is the one that makes someone start a 5 GB download."""
    assert assess_model_fit_bytes(0, 16 * GB) == (None, None)
    assert assess_model_fit_bytes(None, 16 * GB) == (None, None)
    assert assess_model_fit_bytes(4 * GB, 0) == (None, None)
    assert assess_model_fit_bytes(4 * GB, None) == (None, None)


def test_a_big_model_on_a_small_machine_is_refused_plainly():
    code, label = assess_model_fit_bytes(13 * GB, 8 * GB)

    assert code == FIT_TOO_BIG
    assert "Too big" in label
