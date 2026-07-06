"""ledger-worker: double-entry bookkeeping from the payments queue."""


def post_entry(debit: str, credit: str, amount_cents: int) -> None:
    assert amount_cents > 0, "ledger entries must be positive"
    # writes balanced debit/credit rows to the ledger table
