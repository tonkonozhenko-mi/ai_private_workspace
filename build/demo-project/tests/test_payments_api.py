"""The two things the payments API promises: an intent, and a heartbeat."""

from src.api.main import create_intent, health


def test_a_new_intent_waits_for_confirmation():
    intent = create_intent(amount_cents=4200)
    assert intent["status"] == "requires_confirmation"
    assert intent["amount"] == 4200


def test_health_says_ok():
    assert health() == {"ok": True}
