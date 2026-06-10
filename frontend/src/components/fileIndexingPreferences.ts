export type FileIndexingProfile = "balanced" | "source-first" | "docs-first";

export interface FileIndexingPreferences {
  profile: FileIndexingProfile;
  includePatterns: string;
  excludePatterns: string;
}

export interface FileSelectionRulesRequest {
  profile: FileIndexingProfile;
  include_patterns: string[];
  exclude_patterns: string[];
}

export const DEFAULT_INCLUDE_PATTERNS = [
  "src/**",
  "app/**",
  "backend/**",
  "frontend/src/**",
  "docs/**",
  "README*",
  "*.md",
  "*.tf",
  "*.tfvars",
  "terragrunt.hcl",
  "*.yaml",
  "*.yml",
  "Dockerfile",
  "docker-compose*.yml",
  ".github/workflows/**",
  ".gitlab-ci.yml",
  "Jenkinsfile",
  "helm/**",
  "charts/**",
].join("\n");

export const DEFAULT_EXCLUDE_PATTERNS = [
  ".git/**",
  "node_modules/**",
  ".venv/**",
  "venv/**",
  "dist/**",
  "build/**",
  "coverage/**",
  ".pytest_cache/**",
  ".mypy_cache/**",
  "__pycache__/**",
  "*.pyc",
  "*.log",
  "*.lock",
  "*.png",
  "*.jpg",
  "*.jpeg",
  "*.gif",
  "*.zip",
  "*.tar",
  "*.gz",
].join("\n");

export const DEFAULT_FILE_INDEXING_PREFERENCES: FileIndexingPreferences = {
  profile: "balanced",
  includePatterns: DEFAULT_INCLUDE_PATTERNS,
  excludePatterns: DEFAULT_EXCLUDE_PATTERNS,
};

export function normalizeFileIndexingPreferences(
  value: unknown,
): FileIndexingPreferences {
  if (!value || typeof value !== "object") {
    return DEFAULT_FILE_INDEXING_PREFERENCES;
  }

  const candidate = value as Partial<FileIndexingPreferences>;
  return {
    profile: isFileIndexingProfile(candidate.profile)
      ? candidate.profile
      : DEFAULT_FILE_INDEXING_PREFERENCES.profile,
    includePatterns: normalizePatternText(
      candidate.includePatterns,
      DEFAULT_FILE_INDEXING_PREFERENCES.includePatterns,
    ),
    excludePatterns: normalizePatternText(
      candidate.excludePatterns,
      DEFAULT_FILE_INDEXING_PREFERENCES.excludePatterns,
    ),
  };
}

export function normalizePatternText(value: unknown, fallback: string): string {
  if (typeof value !== "string") {
    return fallback;
  }

  const normalized = value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 80)
    .join("\n");

  return normalized || fallback;
}

export function countPatterns(value: string): number {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean).length;
}

function isFileIndexingProfile(value: unknown): value is FileIndexingProfile {
  return value === "balanced" || value === "source-first" || value === "docs-first";
}

export function patternLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function toFileSelectionRulesRequest(
  preferences: FileIndexingPreferences,
): FileSelectionRulesRequest {
  return {
    profile: preferences.profile,
    include_patterns: patternLines(preferences.includePatterns),
    exclude_patterns: patternLines(preferences.excludePatterns),
  };
}
