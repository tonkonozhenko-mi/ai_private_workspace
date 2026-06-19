import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

import { DEFAULT_API_BASE_URL, setApiBaseUrl } from "./api/client";
import {
  DEFAULT_CUSTOM_SKILLS,
  DEFAULT_SKILL_PREFERENCES,
  normalizeCustomSkills,
  normalizeSkillPreferences,
  type CustomSkill,
  type SkillPreferences,
} from "./components/skillLibrary";
import {
  DEFAULT_FILE_INDEXING_PREFERENCES,
  normalizeFileIndexingPreferences,
  type FileIndexingPreferences,
} from "./components/fileIndexingPreferences";
import type { WorkspaceTab } from "./App";

export type ThemePreference = "system" | "light" | "dark";
export type TextSizePreference = "small" | "medium" | "large";
export type SourceSnippetPreference = 3 | 5 | 8 | 10;
export type AccentColorPreference = "green" | "blue" | "purple" | "orange";
export type DemoModePreference = "off" | "on";
export type AnswerCreativityPreference = "precise" | "balanced" | "creative";

export interface WorkbenchPreferences {
  theme: ThemePreference;
  textSize: TextSizePreference;
  defaultReasoning: boolean;
  defaultStreaming: boolean;
  defaultSourceSnippets: SourceSnippetPreference;
  landingTab: WorkspaceTab;
  apiBaseUrl: string;
  brandInitials: string;
  productName: string;
  accentColor: AccentColorPreference;
  demoMode: DemoModePreference;
  developerMode: boolean;
  answerCreativity: AnswerCreativityPreference;
  skillPreferences: SkillPreferences;
  customSkills: CustomSkill[];
  fileIndexingPreferences: FileIndexingPreferences;
}

// Temperature sent to the model per creativity setting. "Precise" is 0.0 on
// purpose: at temperature 0 the model is (near-)deterministic, so asking the
// same question twice gives the same answer — that repeatability is how you can
// actually tell the setting is taking effect. Higher values vary the phrasing.
export const ANSWER_CREATIVITY_TEMPERATURE: Record<AnswerCreativityPreference, number> = {
  precise: 0.0,
  balanced: 0.5,
  creative: 1.0,
};

const PREFERENCES_STORAGE_KEY = "ai-private-workspace.preferences.v1";
const LEGACY_PREFERENCES_STORAGE_KEY = "private-project-ai-workbench.preferences.v1";

export const DEFAULT_PREFERENCES: WorkbenchPreferences = {
  theme: "system",
  textSize: "medium",
  defaultReasoning: false,
  defaultStreaming: true,
  defaultSourceSnippets: 5,
  landingTab: "overview",
  apiBaseUrl: DEFAULT_API_BASE_URL,
  brandInitials: "AI",
  productName: "AI Private Workspace",
  accentColor: "green",
  demoMode: "off",
  developerMode: false,
  answerCreativity: "precise",
  skillPreferences: DEFAULT_SKILL_PREFERENCES,
  customSkills: DEFAULT_CUSTOM_SKILLS,
  fileIndexingPreferences: DEFAULT_FILE_INDEXING_PREFERENCES,
};

// The tabs allowed as a landing/default tab (a subset of WorkspaceTab).
const LANDING_TABS: WorkspaceTab[] = ["overview", "ask", "models", "settings"];

function isThemePreference(value: unknown): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

function isTextSizePreference(value: unknown): value is TextSizePreference {
  return value === "small" || value === "medium" || value === "large";
}

function isSourceSnippetPreference(value: unknown): value is SourceSnippetPreference {
  return value === 3 || value === 5 || value === 8 || value === 10;
}

function isLandingTabPreference(value: unknown): value is WorkspaceTab {
  return (LANDING_TABS as string[]).includes(value as string);
}

function isApiBaseUrlPreference(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function normalizeApiBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function isProductNamePreference(value: unknown): value is string {
  return typeof value === "string" && normalizeProductName(value).length > 0;
}

function normalizeProductName(value: string): string {
  const normalized = value.trim().replace(/\s+/g, " ").slice(0, 48);
  return normalized || "AI Private Workspace";
}

function isBrandInitialsPreference(value: unknown): value is string {
  return typeof value === "string" && normalizeBrandInitials(value).length > 0;
}

function normalizeBrandInitials(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 3) || "AI";
}

function isAccentColorPreference(value: unknown): value is AccentColorPreference {
  return value === "green" || value === "blue" || value === "purple" || value === "orange";
}

function isDemoModePreference(value: unknown): value is DemoModePreference {
  return value === "off" || value === "on";
}

export function loadStoredPreferences(): WorkbenchPreferences {
  try {
    const raw =
      window.localStorage.getItem(PREFERENCES_STORAGE_KEY) ??
      window.localStorage.getItem(LEGACY_PREFERENCES_STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFERENCES;
    }
    const parsed = JSON.parse(raw) as Partial<WorkbenchPreferences>;
    return {
      theme: isThemePreference(parsed.theme) ? parsed.theme : DEFAULT_PREFERENCES.theme,
      textSize: isTextSizePreference(parsed.textSize)
        ? parsed.textSize
        : DEFAULT_PREFERENCES.textSize,
      defaultReasoning:
        typeof parsed.defaultReasoning === "boolean"
          ? parsed.defaultReasoning
          : DEFAULT_PREFERENCES.defaultReasoning,
      defaultStreaming:
        typeof parsed.defaultStreaming === "boolean"
          ? parsed.defaultStreaming
          : DEFAULT_PREFERENCES.defaultStreaming,
      defaultSourceSnippets: isSourceSnippetPreference(parsed.defaultSourceSnippets)
        ? parsed.defaultSourceSnippets
        : DEFAULT_PREFERENCES.defaultSourceSnippets,
      landingTab: isLandingTabPreference(parsed.landingTab)
        ? parsed.landingTab
        : DEFAULT_PREFERENCES.landingTab,
      apiBaseUrl: isApiBaseUrlPreference(parsed.apiBaseUrl)
        ? normalizeApiBaseUrl(parsed.apiBaseUrl)
        : DEFAULT_PREFERENCES.apiBaseUrl,
      brandInitials: isBrandInitialsPreference(parsed.brandInitials)
        ? normalizeBrandInitials(parsed.brandInitials)
        : DEFAULT_PREFERENCES.brandInitials,
      productName: isProductNamePreference(parsed.productName)
        ? normalizeProductName(parsed.productName)
        : DEFAULT_PREFERENCES.productName,
      accentColor: isAccentColorPreference(parsed.accentColor)
        ? parsed.accentColor
        : DEFAULT_PREFERENCES.accentColor,
      demoMode: isDemoModePreference(parsed.demoMode)
        ? parsed.demoMode
        : DEFAULT_PREFERENCES.demoMode,
      developerMode:
        typeof parsed.developerMode === "boolean"
          ? parsed.developerMode
          : DEFAULT_PREFERENCES.developerMode,
      answerCreativity:
        parsed.answerCreativity === "precise" ||
        parsed.answerCreativity === "balanced" ||
        parsed.answerCreativity === "creative"
          ? parsed.answerCreativity
          : DEFAULT_PREFERENCES.answerCreativity,
      skillPreferences: normalizeSkillPreferences(parsed.skillPreferences),
      customSkills: normalizeCustomSkills(parsed.customSkills),
      fileIndexingPreferences: normalizeFileIndexingPreferences(parsed.fileIndexingPreferences),
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

/**
 * Owns the user-preference state: loads it from localStorage (with a legacy-key
 * fallback) on first render, persists every change, and applies the visual
 * preferences (theme, text size, accent, demo mode) and the API base URL.
 * Extracted from App.tsx so the root component is no longer responsible for
 * preference plumbing.
 */
export function usePreferences(): {
  preferences: WorkbenchPreferences;
  setPreferences: Dispatch<SetStateAction<WorkbenchPreferences>>;
} {
  const [preferences, setPreferences] = useState<WorkbenchPreferences>(() =>
    loadStoredPreferences(),
  );

  useEffect(() => {
    window.localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.dataset.textSize = preferences.textSize;
    setApiBaseUrl(preferences.apiBaseUrl);
    document.documentElement.dataset.accent = preferences.accentColor;
    document.documentElement.dataset.demoMode = preferences.demoMode;
  }, [preferences]);

  return { preferences, setPreferences };
}
