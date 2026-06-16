from dataclasses import dataclass

from app.core.domain.command import CommandRisk

AUTO_EXECUTABLE_READONLY_PREFIXES = [
    "git status",
    "git diff",
    "git log",
    "git show",
    "git branch",
    "terraform validate",
    "terraform plan",
    "terragrunt validate",
    "terragrunt plan",
    "helm lint",
    "helm template",
    "grep",
]

SHELL_OPERATOR_FRAGMENTS = [";", "&&", "||", "|", "`", "$("]


@dataclass(frozen=True)
class CommandPolicyDecision:
    allowed: bool
    mode: str
    reason: str
    matched_rule: str | None


def evaluate_command_policy(command: str, risk: str) -> CommandPolicyDecision:
    normalized_command = " ".join(command.strip().lower().split())

    if risk == CommandRisk.DESTRUCTIVE.value:
        return CommandPolicyDecision(
            allowed=False,
            mode="blocked",
            reason="Destructive commands are blocked by policy.",
            matched_rule="block_destructive",
        )

    if any(fragment in command for fragment in SHELL_OPERATOR_FRAGMENTS):
        return CommandPolicyDecision(
            allowed=False,
            mode="blocked",
            reason="Compound shell commands are blocked by policy.",
            matched_rule="block_shell_operators",
        )

    if risk == CommandRisk.READONLY.value and any(
        _starts_with_command(normalized_command, prefix)
        for prefix in AUTO_EXECUTABLE_READONLY_PREFIXES
    ):
        return CommandPolicyDecision(
            allowed=True,
            mode="auto_executable",
            reason="Command is read-only and allowed by policy.",
            matched_rule="readonly_allowlist",
        )

    if risk == CommandRisk.WRITE.value:
        return CommandPolicyDecision(
            allowed=False,
            mode="manual_only",
            reason="Write commands require manual execution outside the assistant.",
            matched_rule="write_manual_only",
        )

    if risk == CommandRisk.UNKNOWN.value:
        return CommandPolicyDecision(
            allowed=False,
            mode="manual_only",
            reason="Unknown-risk commands require manual execution outside the assistant.",
            matched_rule="unknown_manual_only",
        )

    return CommandPolicyDecision(
        allowed=False,
        mode="manual_only",
        reason="Command is not allowed for automatic execution.",
        matched_rule="fallback_manual_only",
    )


def _starts_with_command(command: str, prefix: str) -> bool:
    return command == prefix or command.startswith(f"{prefix} ")
