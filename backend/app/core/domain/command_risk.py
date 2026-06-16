from app.core.domain.command import CommandRisk

READONLY_PREFIXES = [
    "git status",
    "git diff",
    "git log",
    "git show",
    "git branch",
    "ls",
    "pwd",
    "cat",
    "grep",
    "terraform plan",
    "terraform validate",
    "terragrunt plan",
    "terragrunt validate",
    "helm template",
    "helm lint",
]

DESTRUCTIVE_CONTAINS = [
    "rm -rf",
    "git reset --hard",
    "git push",
    "terraform apply",
    "terraform destroy",
    "terragrunt apply",
    "terragrunt destroy",
    "kubectl delete",
    "kubectl apply",
    "helm uninstall",
]

WRITE_PREFIXES = [
    "git checkout",
    "git pull",
    "git merge",
    "git rebase",
    "mkdir",
    "touch",
    "cp",
    "mv",
]


def classify_command_risk(command: str) -> str:
    normalized_command = " ".join(command.strip().lower().split())

    if any(fragment in normalized_command for fragment in DESTRUCTIVE_CONTAINS):
        return CommandRisk.DESTRUCTIVE.value

    if any(_starts_with_command(normalized_command, prefix) for prefix in READONLY_PREFIXES):
        return CommandRisk.READONLY.value

    if any(_starts_with_command(normalized_command, prefix) for prefix in WRITE_PREFIXES):
        return CommandRisk.WRITE.value

    return CommandRisk.UNKNOWN.value


def _starts_with_command(command: str, prefix: str) -> bool:
    return command == prefix or command.startswith(f"{prefix} ")
