from app.core.domain.command_policy import evaluate_command_policy


def test_destructive_command_is_blocked() -> None:
    decision = evaluate_command_policy("terraform apply", "destructive")

    assert decision.allowed is False
    assert decision.mode == "blocked"
    assert decision.reason == "Destructive commands are blocked by policy."
    assert decision.matched_rule == "block_destructive"


def test_compound_shell_command_is_blocked() -> None:
    decision = evaluate_command_policy("git status && git diff", "readonly")

    assert decision.allowed is False
    assert decision.mode == "blocked"
    assert decision.reason == "Compound shell commands are blocked by policy."
    assert decision.matched_rule == "block_shell_operators"


def test_readonly_allowlisted_command_is_auto_executable() -> None:
    decision = evaluate_command_policy("git status --short", "readonly")

    assert decision.allowed is True
    assert decision.mode == "auto_executable"
    assert decision.reason == "Command is read-only and allowed by policy."
    assert decision.matched_rule == "readonly_allowlist"


def test_write_command_is_manual_only() -> None:
    decision = evaluate_command_policy("git checkout main", "write")

    assert decision.allowed is False
    assert decision.mode == "manual_only"
    assert decision.reason == "Write commands require manual execution outside the assistant."
    assert decision.matched_rule == "write_manual_only"


def test_unknown_command_is_manual_only() -> None:
    decision = evaluate_command_policy("python scripts/check.py", "unknown")

    assert decision.allowed is False
    assert decision.mode == "manual_only"
    assert (
        decision.reason == "Unknown-risk commands require manual execution outside the assistant."
    )
    assert decision.matched_rule == "unknown_manual_only"
