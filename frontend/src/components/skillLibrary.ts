// The five canonical roles, used everywhere (Settings skills, the Intelligence
// "Viewed as" lens, and the Ask answer style). One vocabulary, one set of names.
export type SkillPresetId =
  | "developer"
  | "devops"
  | "tester"
  | "business_analyst"
  | "manager";

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

export type SkillProfileTemplateId =
  | "developer_review"
  | "devops_review"
  | "tester_review"
  | "business_analyst_review"
  | "manager_review";

export interface SkillProfileTemplateDefinition {
  id: SkillProfileTemplateId;
  name: string;
  shortName: string;
  purpose: string;
  activeSkillIds: SkillPresetId[];
  guidance: Partial<Record<SkillPresetId, string>>;
}

export const SKILL_PRESETS: SkillPresetDefinition[] = [
  {
    id: "developer",
    name: "Developer",
    shortName: "Developer",
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
    id: "tester",
    name: "Tester / QA",
    shortName: "Tester",
    purpose: "Test coverage, test types, critical flows, regression-risk areas, and edge cases.",
    bestFor: "What is tested and how, the riskiest flows to verify, gaps in coverage, and what to re-test after a change.",
    exampleQuestions: [
      "Which critical flows should I test?",
      "Where is test coverage thin?",
      "What should I re-test after this change?",
    ],
    defaultInstructions: "Answer as a QA / test engineer. Focus on test coverage and test types, the critical flows to verify, regression-risk areas, edge cases, and what to test after a change.",
    recommendedFiles: ["tests/**", "test/**", "**/*_test.*", "**/*.spec.*", ".github/workflows/**"],
  },
  {
    id: "business_analyst",
    name: "Business analyst",
    shortName: "Analyst",
    purpose: "What the system does, business processes, user flows, entities, integrations, and rules.",
    bestFor: "Plain-language understanding of features, the main entities and flows, integrations, business rules, and open questions.",
    exampleQuestions: [
      "What does this system do for its users?",
      "What are the main entities and flows?",
      "Which integrations and rules matter here?",
    ],
    defaultInstructions: "Answer as a business analyst. Explain in plain language what the system does, its main entities and user flows, integrations, business rules, and the open questions worth clarifying.",
    recommendedFiles: ["README*", "docs/**", "*.md", "src/**"],
  },
  {
    id: "manager",
    name: "Manager",
    shortName: "Manager",
    purpose: "Executive summary, project health, main risks, recent changes, ownership, and delivery.",
    bestFor: "Status updates, risk summaries, ownership and recent changes, decisions, and stakeholder-friendly wording.",
    exampleQuestions: [
      "Summarize the project status for stakeholders.",
      "What are the main risks?",
      "What changed recently, and who owns what?",
    ],
    defaultInstructions: "Answer for an engineering manager. Focus on a concise executive summary, project health, the main risks, recent changes, ownership, delivery flow, and stakeholder-friendly wording.",
    recommendedFiles: ["README*", "docs/**", "reports/**", "*.md"],
  },
];

export const SKILL_PROFILE_TEMPLATES: SkillProfileTemplateDefinition[] = [
  {
    id: "developer_review",
    name: "Developer review",
    shortName: "Developer",
    purpose: "Review application structure, tests, dependencies, code risks, and change impact.",
    activeSkillIds: ["developer"],
    guidance: {
      developer:
        "Review this workspace as a developer assistant. Focus on source code structure, key modules, dependencies, tests, change impact, and concrete next steps. Keep project-specific claims grounded in retrieved sources.",
    },
  },
  {
    id: "devops_review",
    name: "DevOps review",
    shortName: "DevOps",
    purpose: "Review infrastructure, CI/CD, deployments, runtime setup, and operational risks.",
    activeSkillIds: ["devops"],
    guidance: {
      devops:
        "Review this workspace as a DevOps/platform assistant. Focus on infrastructure, CI/CD, deployment flow, local runtime, automation safety, observability, and practical risks. Keep project-specific claims grounded in retrieved sources.",
    },
  },
  {
    id: "tester_review",
    name: "Tester / QA review",
    shortName: "Tester",
    purpose: "Review test coverage, critical flows, regression-risk areas, and edge cases.",
    activeSkillIds: ["tester"],
    guidance: {
      tester:
        "Review this workspace as a QA / test engineer. Focus on test coverage and types, the critical flows to verify, regression-risk areas, edge cases, and what to test after a change. Keep project-specific claims grounded in retrieved sources.",
    },
  },
  {
    id: "business_analyst_review",
    name: "Business analyst review",
    shortName: "Analyst",
    purpose: "Review what the system does, entities, user flows, integrations, and business rules.",
    activeSkillIds: ["business_analyst"],
    guidance: {
      business_analyst:
        "Review this workspace as a business analyst. Explain in plain language what the system does, its main entities and user flows, integrations, business rules, and the open questions worth clarifying. Keep project-specific claims grounded in retrieved sources.",
    },
  },
  {
    id: "manager_review",
    name: "Manager review",
    shortName: "Manager",
    purpose: "Prepare a concise status, the main risks, recent changes, ownership, and decisions.",
    activeSkillIds: ["manager"],
    guidance: {
      manager:
        "Review this workspace for an engineering manager. Focus on a concise executive summary, project health, the main risks, recent changes, ownership, delivery flow, and stakeholder-friendly wording. Keep project-specific claims grounded in retrieved sources.",
    },
  },
];

export function applySkillProfileTemplate(
  templateId: SkillProfileTemplateId,
  currentPreferences: SkillPreferences = DEFAULT_SKILL_PREFERENCES,
): SkillPreferences {
  const template = SKILL_PROFILE_TEMPLATES.find((item) => item.id === templateId);
  if (!template) {
    return normalizeSkillPreferences(currentPreferences);
  }

  return SKILL_PRESETS.reduce((preferences, preset) => {
    const templateInstruction = template.guidance[preset.id];
    preferences[preset.id] = {
      enabled: template.activeSkillIds.includes(preset.id),
      customInstructions:
        templateInstruction ??
        currentPreferences[preset.id]?.customInstructions ??
        preset.defaultInstructions,
    };
    return preferences;
  }, {} as SkillPreferences);
}

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

// User-created skills (beyond the built-in presets). Lightweight prompt
// guidance: a name + instructions that shape the answer's tone and focus.
export interface CustomSkill {
  id: string;
  name: string;
  instructions: string;
}

export const DEFAULT_CUSTOM_SKILLS: CustomSkill[] = [];

export function makeCustomSkillId(): string {
  return `custom-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`}`;
}

export function normalizeCustomSkills(value: unknown): CustomSkill[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const skills: CustomSkill[] = [];
  for (const raw of value) {
    if (!raw || typeof raw !== "object") {
      continue;
    }
    const item = raw as Partial<CustomSkill>;
    const name = typeof item.name === "string" ? item.name.trim().slice(0, 80) : "";
    const instructions =
      typeof item.instructions === "string" ? item.instructions.slice(0, 1200) : "";
    if (!name || !instructions.trim()) {
      continue;
    }
    skills.push({
      id: typeof item.id === "string" && item.id ? item.id : makeCustomSkillId(),
      name,
      instructions,
    });
    if (skills.length >= 20) {
      break;
    }
  }
  return skills;
}

export function getEnabledSkillPresets(preferences: SkillPreferences): SkillPresetDefinition[] {
  return SKILL_PRESETS.filter((preset) => preferences[preset.id]?.enabled);
}

export function getSkillPresetByAssistantMode(mode: string): SkillPresetDefinition {
  const normalizedMode = mode === "support_incident" ? "incident_support" : mode;
  return SKILL_PRESETS.find((preset) => preset.id === normalizedMode) ?? SKILL_PRESETS[0];
}


export function toSkillProfileRequest(preferences: SkillPreferences) {
  return {
    profile: "workspace",
    skills: SKILL_PRESETS.map((preset) => ({
      id: preset.id,
      name: preset.name,
      enabled: Boolean(preferences[preset.id]?.enabled),
      custom_instructions:
        preferences[preset.id]?.customInstructions.trim() || preset.defaultInstructions,
    })),
  };
}

// Make one role the single active skill, so the workspace's role and the Ask
// answer style stay the same thing. Other skills keep their saved instructions
// but are turned off; an unknown mode leaves preferences unchanged.
export function skillPreferencesForRole(
  mode: string,
  current: SkillPreferences = DEFAULT_SKILL_PREFERENCES,
): SkillPreferences {
  const base = normalizeSkillPreferences(current);
  if (!SKILL_PRESETS.some((preset) => preset.id === mode)) {
    return base;
  }
  return SKILL_PRESETS.reduce((preferences, preset) => {
    preferences[preset.id] = {
      enabled: preset.id === mode,
      customInstructions: base[preset.id].customInstructions,
    };
    return preferences;
  }, {} as SkillPreferences);
}

export function skillPreferencesFromProfile(value: unknown): SkillPreferences {
  if (!value || typeof value !== "object" || !("skills" in value)) {
    return DEFAULT_SKILL_PREFERENCES;
  }
  const profile = value as { skills?: Array<{ id?: string; enabled?: boolean; custom_instructions?: string }> };
  const raw = profile.skills?.reduce((accumulator, item) => {
    if (typeof item.id === "string") {
      accumulator[item.id as SkillPresetId] = {
        enabled: Boolean(item.enabled),
        customInstructions: typeof item.custom_instructions === "string" ? item.custom_instructions : "",
      };
    }
    return accumulator;
  }, {} as Partial<Record<SkillPresetId, Partial<SkillPreference>>>) ?? {};
  return normalizeSkillPreferences(raw);
}
