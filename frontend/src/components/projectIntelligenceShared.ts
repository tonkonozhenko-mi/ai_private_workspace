// Shared detection patterns for Project Intelligence, used by both the main
// orchestrator (to decide which tabs to show) and the section components.
// Security-relevant concepts, detected generically by token — no project- or
// vendor-specific hardcoding beyond well-known scanner names that work anywhere.
export const SCANNER_RE = /scan|security|audit|trivy|checkov|gitleaks|secret|sonar|snyk|semgrep|bandit|tfsec|dependabot|codeql|vuln/i;
export const SECURITY_FINDING_RE = /secret|credential|password|permission|public|expos|encrypt|unencrypted|iam|access|policy|ssl|tls|cors|privileg|remote[_ ]state|0\.0\.0\.0|firewall|port|auth/i;
