export type SkillPresetId =
  | "devops"
  | "developer"
  | "documentation"
  | "incident_support"
  | "manager_summary";

export interface SkillPresetDefinition {
  id: SkillPresetId;
  name: string;
  shortName: string;
  purpose: string;
  bestFor: string;
  exampleQuestions: string[];
  defaultInstructions: string;
  recommendedFiles: string[];
}

export interface SkillPreference {
  enabled: boolean;
  customInstructions: string;
}

export type SkillPreferences = Record<SkillPresetId, SkillPreference>;

export const SKILL_PRESETS: SkillPresetDefinition[] = [
  {
    id: "devops",
    name: "DevOps",
    shortName: "DevOps",
    purpose: "Infrastructure, CI/CD, cloud, containers, runtime setup, and operational readiness.",
    bestFor: "Terraform, Terragrunt, Kubernetes, Docker, Helm, Jenkins, GitHub Actions, GitLab CI, deployment flow, and runtime configuration.",
    exampleQuestions: [
      "How is Terraform backend configured?",
      "Which CI/CD systems are detected?",
      "What should I review before deployment?",
    ],
    defaultInstructions: "Answer as a DevOps/platform assistant. Pay attention to infrastructure, CI/CD, Terraform, Terragrunt, Kubernetes, Docker, Helm, Jenkins pipelines, GitHub Actions, GitLab CI, runtime configuration, and deployment risks.",
    recommendedFiles: ["*.tf", "terragrunt.hcl", "Dockerfile", "helm/**", ".github/workflows/**", ".gitlab-ci.yml", "Jenkinsfile"],
  },
  {
    id: "developer",
    name: "Developer",
    shortName: "Code",
    purpose: "Application code, structure, dependencies, implementation details, and tests.",
    bestFor: "Source code navigation, service boundaries, test coverage, dependencies, and change impact.",
    exampleQuestions: [
      "Where is the main application entry point?",
      "What tests cover this module?",
      "What code areas are risky to change?",
    ],
    defaultInstructions: "Answer as a developer assistant. Focus on source code structure, implementation details, dependencies, tests, change impact, and practical next steps.",
    recommendedFiles: ["src/**", "tests/**", "package.json", "pom.xml", "build.gradle", "requirements.txt"],
  },
  {
    id: "documentation",
    name: "Documentation",
    shortName: "Docs",
    purpose: "README files, architecture notes, onboarding material, and project summaries.",
    bestFor: "Project overview, missing documentation, onboarding plans, architecture notes, and user-friendly summaries.",
    exampleQuestions: [
      "What should be added to the README?",
      "Summarize this project for onboarding.",
      "Which architecture notes are missing?",
    ],
    defaultInstructions: "Answer as a documentation assistant. Focus on clear explanations, onboarding quality, README gaps, architecture notes, and concise project summaries.",
    recommendedFiles: ["README*", "docs/**", "architecture/**", "*.md"],
  },
  {
    id: "incident_support",
    name: "Incident Support",
    shortName: "Support",
    purpose: "Troubleshooting, logs, symptoms, likely causes, and operational checks.",
    bestFor: "Incident review, support runbooks, logs, alerts, symptoms, and next investigation steps.",
    exampleQuestions: [
      "What should I check first for this error?",
      "Which files look relevant for troubleshooting?",
      "What could cause this deployment failure?",
    ],
    defaultInstructions: "Answer as an incident support assistant. Focus on symptoms, likely causes, operational checks, logs, rollback risks, and step-by-step troubleshooting.",
    recommendedFiles: ["logs/**", "runbooks/**", "alerts/**", "docs/**", "*.md"],
  },
  {
    id: "manager_summary",
    name: "Manager Summary",
    shortName: "Summary",
    purpose: "High-level summaries, risks, progress, decisions, and stakeholder-friendly wording.",
    bestFor: "Status updates, risk summaries, decision notes, demos, and concise management communication.",
    exampleQuestions: [
      "Summarize the project status for stakeholders.",
      "What are the main risks?",
      "What should I mention in a demo?",
    ],
    defaultInstructions: "Answer as a manager-summary assistant. Focus on concise summaries, risks, progress, decisions, business impact, and stakeholder-friendly wording.",
    recommendedFiles: ["README*", "docs/**", "reports/**", "*.md"],
  },
];

export const DEFAULT_SKILL_PREFERENCES: SkillPreferences = SKILL_PRESETS.reduce(
  (preferences, preset) => {
    preferences[preset.id] = {
      enabled: preset.id === "devops",
      customInstructions: preset.defaultInstructions,
    };
    return preferences;
  },
  {} as SkillPreferences,
);

export function normalizeSkillPreferences(value: unknown): SkillPreferences {
  const parsed = value && typeof value === "object" && !Array.isArray(value)
    ? (value as Partial<Record<SkillPresetId, Partial<SkillPreference>>>)
    : {};

  return SKILL_PRESETS.reduce((preferences, preset) => {
    const incoming = parsed[preset.id];
    const enabled = typeof incoming?.enabled === "boolean"
      ? incoming.enabled
      : DEFAULT_SKILL_PREFERENCES[preset.id].enabled;
    const customInstructions = typeof incoming?.customInstructions === "string"
      ? incoming.customInstructions.slice(0, 1200)
      : DEFAULT_SKILL_PREFERENCES[preset.id].customInstructions;

    preferences[preset.id] = { enabled, customInstructions };
    return preferences;
  }, {} as SkillPreferences);
}

export function getEnabledSkillPresets(preferences: SkillPreferences): SkillPresetDefinition[] {
  return SKILL_PRESETS.filter((preset) => preferences[preset.id]?.enabled);
}

export function getSkillPresetByAssistantMode(mode: string): SkillPresetDefinition {
  const normalizedMode = mode === "support_incident" ? "incident_support" : mode;
  return SKILL_PRESETS.find((preset) => preset.id === normalizedMode) ?? SKILL_PRESETS[0];
}
