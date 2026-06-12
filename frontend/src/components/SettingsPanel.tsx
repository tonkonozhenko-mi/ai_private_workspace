import { useMemo, useState, type FormEvent } from "react";

import type { WorkbenchPreferences } from "../App";
import {
  previewWorkspaceFileSelection,
  updateWorkspaceIndexingRules,
  updateWorkspaceSkillProfile,
} from "../api/client";
import type {
  WorkspaceDashboard as WorkspaceDashboardData,
  WorkspaceModelsDashboardSummary,
  FileSelectionPreview,
} from "../api/types";
import {
  countPatterns,
  normalizePatternText,
  toFileSelectionRulesRequest,
} from "./fileIndexingPreferences";
import { StatusBadge } from "./StatusBadge";
import {
  SKILL_PRESETS,
  SKILL_PROFILE_TEMPLATES,
  applySkillProfileTemplate,
  normalizeSkillPreferences,
  toSkillProfileRequest,
  type SkillPresetId,
  type SkillPreferences,
  type SkillProfileTemplateId,
} from "./skillLibrary";

interface SettingsPanelProps {
  dashboard: WorkspaceDashboardData;
  modelsSummary: WorkspaceModelsDashboardSummary;
  preferences: WorkbenchPreferences;
  onPreferencesChange: (preferences: WorkbenchPreferences) => void;
  onResetPreferences: () => void;
  onOpenModels: () => void;
  onIndexingRulesSaved?: () => void;
  skillProfileSource?: string;
  skillProfileUpdatedAt?: string | null;
  onSkillProfileSaved?: () => void;
}

const SKILL_TEMPLATES: Array<{
  id: SkillProfileTemplateId;
  title: string;
  description: string;
}> = [
  {
    id: "devops_review",
    title: "DevOps review",
    description: "Infrastructure, CI/CD, Kubernetes, Terraform, runtime and deployment questions.",
  },
  {
    id: "code_review",
    title: "Developer review",
    description: "Application code, tests, architecture, modules and implementation questions.",
  },
  {
    id: "documentation_review",
    title: "Documentation review",
    description: "README, onboarding, design notes, summaries and project explanation.",
  },
  {
    id: "incident_support",
    title: "Incident support",
    description: "Troubleshooting, logs, likely causes, operational checks and rollback risks.",
  },
  {
    id: "manager_summary",
    title: "Manager summary",
    description: "Short summaries, risks, decisions and stakeholder-friendly wording.",
  },
];

export function SettingsPanel({
  dashboard,
  modelsSummary,
  preferences,
  onPreferencesChange,
  onResetPreferences,
  onOpenModels,
  onIndexingRulesSaved,
  skillProfileSource = "default",
  skillProfileUpdatedAt = null,
  onSkillProfileSaved,
}: SettingsPanelProps) {
  const [fileRulesDraft, setFileRulesDraft] = useState(() => ({
    includePatterns: preferences.fileIndexingPreferences.includePatterns,
    excludePatterns: preferences.fileIndexingPreferences.excludePatterns,
  }));
  const [fileRulesMessage, setFileRulesMessage] = useState("Saved file rules are used by Scan and Build context.");
  const [savingFileRules, setSavingFileRules] = useState(false);
  const [fileRulesPreview, setFileRulesPreview] = useState<FileSelectionPreview | null>(null);
  const [previewingFileRules, setPreviewingFileRules] = useState(false);
  const [skillDrafts, setSkillDrafts] = useState<Record<SkillPresetId, string>>(() =>
    buildSkillDrafts(preferences.skillPreferences),
  );
  const [skillMessage, setSkillMessage] = useState("Ask uses this workspace guidance when preparing answers.");
  const [savingSkills, setSavingSkills] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<SkillProfileTemplateId>("devops_review");

  const includeCount = countPatterns(fileRulesDraft.includePatterns);
  const excludeCount = countPatterns(fileRulesDraft.excludePatterns);
  const selectedTemplate = useMemo(
    () => SKILL_TEMPLATES.find((template) => template.id === selectedTemplateId) ?? SKILL_TEMPLATES[0],
    [selectedTemplateId],
  );
  const selectedTemplateDefinition = useMemo(
    () => SKILL_PROFILE_TEMPLATES.find((template) => template.id === selectedTemplateId),
    [selectedTemplateId],
  );
  const selectedSkillPresets = useMemo(() => {
    const ids = selectedTemplateDefinition?.activeSkillIds ?? ["devops"];
    return SKILL_PRESETS.filter((preset) => ids.includes(preset.id));
  }, [selectedTemplateDefinition]);
  const contextReady = dashboard.summary.index_status.status === "indexed";
  const modelsReady = modelsSummary.overall_status === "ready";

  function updatePreference(patch: Partial<WorkbenchPreferences>) {
    onPreferencesChange({ ...preferences, ...patch });
  }

  async function saveFileRules(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSavingFileRules(true);
    setFileRulesMessage("Saving file rules…");
    try {
      const normalized = {
        profile: preferences.fileIndexingPreferences.profile,
        includePatterns: normalizePatternText(fileRulesDraft.includePatterns, preferences.fileIndexingPreferences.includePatterns),
        excludePatterns: normalizePatternText(fileRulesDraft.excludePatterns, preferences.fileIndexingPreferences.excludePatterns),
      };
      await updateWorkspaceIndexingRules(
        dashboard.workspace_id,
        toFileSelectionRulesRequest(normalized),
      );
      updatePreference({ fileIndexingPreferences: normalized });
      setFileRulesMessage("Saved. Rebuild context when you want these rules to affect Ask.");
      onIndexingRulesSaved?.();
    } catch (error) {
      setFileRulesMessage(errorMessage(error));
    } finally {
      setSavingFileRules(false);
    }
  }

  async function previewFileRules() {
    setPreviewingFileRules(true);
    setFileRulesMessage("Previewing file selection…");
    try {
      const normalized = {
        profile: preferences.fileIndexingPreferences.profile,
        includePatterns: normalizePatternText(fileRulesDraft.includePatterns, preferences.fileIndexingPreferences.includePatterns),
        excludePatterns: normalizePatternText(fileRulesDraft.excludePatterns, preferences.fileIndexingPreferences.excludePatterns),
      };
      const preview = await previewWorkspaceFileSelection(
        dashboard.workspace_id,
        toFileSelectionRulesRequest(normalized),
      );
      setFileRulesPreview(preview);
      setFileRulesMessage(`${preview.included_files_count} files would be included.`);
    } catch (error) {
      setFileRulesMessage(errorMessage(error));
    } finally {
      setPreviewingFileRules(false);
    }
  }

  async function saveSkillGuidance() {
    const nextSkillPreferences: SkillPreferences = normalizeSkillPreferences({
      ...preferences.skillPreferences,
      customInstructions: skillDrafts,
    });
    setSavingSkills(true);
    setSkillMessage("Saving workspace guidance…");
    try {
      await updateWorkspaceSkillProfile(
        dashboard.workspace_id,
        toSkillProfileRequest(nextSkillPreferences),
      );
      updatePreference({ skillPreferences: nextSkillPreferences });
      setSkillMessage("Saved. Ask will use this guidance for the workspace.");
      onSkillProfileSaved?.();
    } catch (error) {
      setSkillMessage(errorMessage(error));
    } finally {
      setSavingSkills(false);
    }
  }

  function applyTemplate() {
    const next = applySkillProfileTemplate(selectedTemplateId, preferences.skillPreferences);
    setSkillDrafts(buildSkillDrafts(next));
    updatePreference({ skillPreferences: next });
    setSkillMessage(`${selectedTemplate.title} template applied. Save to workspace to persist it.`);
  }

  return (
    <div className="settings-simplified-page">
      <section className="panel settings-clean-hero">
        <div>
          <p className="eyebrow">Settings</p>
          <h2>Keep daily use simple.</h2>
          <p>Change only daily-use preferences. Model setup lives in Models, and advanced diagnostics stay out of the main flow.</p>
        </div>
        <div className="settings-clean-status">
          <StatusBadge label={contextReady ? "Context ready" : "Context needs build"} />
          <StatusBadge label={modelsReady ? "Models ready" : "Models need review"} />
        </div>
      </section>

      <section className="settings-clean-grid">
        <article className="panel settings-clean-card">
          <div className="panel-heading compact-heading">
            <div>
              <p className="eyebrow">Appearance</p>
              <h3>Look and feel</h3>
            </div>
          </div>
          <div className="segmented-control" aria-label="Theme">
            {(["system", "light", "dark"] as const).map((theme) => (
              <button
                key={theme}
                type="button"
                className={preferences.theme === theme ? "is-selected" : ""}
                onClick={() => updatePreference({ theme })}
              >
                {formatLabel(theme)}
              </button>
            ))}
          </div>
          <div className="segmented-control" aria-label="Density">
            {(["comfortable", "compact"] as const).map((density) => (
              <button
                key={density}
                type="button"
                className={preferences.density === density ? "is-selected" : ""}
                onClick={() => updatePreference({ density })}
              >
                {formatLabel(density)}
              </button>
            ))}
          </div>
          <button className="secondary-action" type="button" onClick={onResetPreferences}>
            Reset appearance
          </button>
        </article>
      </section>

      <section className="panel settings-clean-card">
        <div className="panel-heading compact-heading">
          <div>
            <p className="eyebrow">Project files</p>
            <h3>What Scan and Build context should read</h3>
            <p className="panel-helper">
              These rules stay local. Keep them broad for normal use; narrow them only when the project is too large.
            </p>
          </div>
          <StatusBadge label={`${includeCount} include · ${excludeCount} exclude`} />
        </div>
        <form className="settings-clean-file-form" onSubmit={(event) => void saveFileRules(event)}>
          <label>
            <span>Include patterns</span>
            <textarea
              value={fileRulesDraft.includePatterns}
              onChange={(event) => setFileRulesDraft((current) => ({ ...current, includePatterns: event.target.value }))}
              rows={5}
              spellCheck={false}
            />
          </label>
          <label>
            <span>Exclude patterns</span>
            <textarea
              value={fileRulesDraft.excludePatterns}
              onChange={(event) => setFileRulesDraft((current) => ({ ...current, excludePatterns: event.target.value }))}
              rows={5}
              spellCheck={false}
            />
          </label>
          <div className="settings-clean-actions">
            <button className="primary-button" type="submit" disabled={savingFileRules}>
              {savingFileRules ? "Saving…" : "Save file rules"}
            </button>
            <button className="secondary-action" type="button" disabled={previewingFileRules} onClick={() => void previewFileRules()}>
              {previewingFileRules ? "Previewing…" : "Preview files"}
            </button>
          </div>
        </form>
        <p className="settings-message">{fileRulesMessage}</p>
        {fileRulesPreview ? (
          <div className="settings-clean-preview">
            <strong>{fileRulesPreview.included_files_count} files included</strong>
            <span>{fileRulesPreview.excluded_files_count} excluded · {fileRulesPreview.total_files} seen</span>
          </div>
        ) : null}
      </section>

      <section className="panel settings-clean-card">
        <div className="panel-heading compact-heading">
          <div>
            <p className="eyebrow">Ask guidance</p>
            <h3>How the assistant should read this workspace</h3>
            <p className="panel-helper">
              Source: {skillProfileSource}{skillProfileUpdatedAt ? ` · updated ${formatDate(skillProfileUpdatedAt)}` : ""}
            </p>
          </div>
        </div>
        <div className="settings-clean-template-row">
          <select value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value as SkillProfileTemplateId)}>
            {SKILL_TEMPLATES.map((template) => (
              <option key={template.id} value={template.id}>{template.title}</option>
            ))}
          </select>
          <button className="secondary-action" type="button" onClick={applyTemplate}>
            Apply template
          </button>
        </div>
        <p className="panel-helper">{selectedTemplate.description}</p>
        <div className="settings-selected-guidance-card">
          <div>
            <p className="eyebrow">Active guidance</p>
            <strong>{selectedTemplate.title}</strong>
            <span>{selectedSkillPresets.map((preset) => preset.name).join(" + ")}</span>
          </div>
          <p>Only the guidance used by the selected template is shown here. Other assistant styles stay hidden until you choose them.</p>
        </div>
        <div className="settings-clean-guidance-list settings-clean-guidance-list-focused">
          {selectedSkillPresets.map((preset) => (
            <label key={preset.id}>
              <span>{preset.name}</span>
              <small>{preset.purpose}</small>
              <textarea
                rows={4}
                value={skillDrafts[preset.id] ?? ""}
                onChange={(event) =>
                  setSkillDrafts((current) => ({ ...current, [preset.id]: event.target.value }))
                }
              />
            </label>
          ))}
        </div>
        <div className="settings-clean-actions">
          <button className="primary-button" type="button" disabled={savingSkills} onClick={() => void saveSkillGuidance()}>
            {savingSkills ? "Saving…" : "Save Ask guidance"}
          </button>
        </div>
        <p className="settings-message">{skillMessage}</p>
      </section>
    </div>
  );
}

function buildSkillDrafts(preferences: SkillPreferences): Record<SkillPresetId, string> {
  const drafts = {} as Record<SkillPresetId, string>;
  for (const preset of SKILL_PRESETS) {
    drafts[preset.id] = preferences[preset.id]?.customInstructions ?? preset.defaultInstructions;
  }
  return drafts;
}

function formatLabel(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  } catch {
    return value;
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected request error";
}
