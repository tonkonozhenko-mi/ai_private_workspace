"""Every entry the ledger posts must be positive and must balance."""

import pytest

from src.workers.ledger import post_entry


def test_a_positive_entry_is_accepted():
    post_entry(debit="cash", credit="revenue", amount_cents=1250)


def test_a_zero_or_negative_entry_is_refused():
    with pytest.raises(AssertionError):
        post_entry(debit="cash", credit="revenue", amount_cents=0)


@pytest.mark.skip(reason="needs a real ledger table; runs in the integration suite")
def test_entries_are_written_in_pairs():
    ...
