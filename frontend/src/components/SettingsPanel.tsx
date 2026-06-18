import { useMemo, useState, type FormEvent } from "react";

import type { WorkbenchPreferences } from "../App";
import {
  deleteWorkspace,
  getWorkspacesOverview,
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
  normalizeSkillPreferences,
  toSkillProfileRequest,
  type SkillPresetId,
  makeCustomSkillId,
  type CustomSkill,
  type SkillPreferences,
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
  // Skills editor: one selector drives which skill is shown/edited.
  // Value is a preset id, a custom-skill id, or "__new__" to create one.
  const [selectedSkillKey, setSelectedSkillKey] = useState<string>(SKILL_PRESETS[0].id);
  const [newSkillName, setNewSkillName] = useState("");
  const [newSkillInstructions, setNewSkillInstructions] = useState("");
  const [confirmingReset, setConfirmingReset] = useState<null | "settings" | "workspaces">(null);
  const [resetting, setResetting] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  // Reset settings only: restores every app preference (theme, developer mode,
  // accent, skills, file rules, …) to defaults. Projects and their index stay.
  function resetSettings() {
    onResetPreferences();
    setConfirmingReset(null);
    setResetMessage("App settings restored to defaults. Your projects are untouched.");
  }

  // Reset projects only: removes all workspaces and their local index, returning
  // to the first-run screen. Settings stay. Project files on disk and installed
  // Ollama models are never touched.
  async function resetWorkspaces() {
    setResetting(true);
    setResetMessage(null);
    try {
      const overview = await getWorkspacesOverview();
      for (const item of overview.items) {
        await deleteWorkspace(item.workspace_id);
      }
      setResetMessage(
        `Removed ${overview.items.length} project(s) and their local index data. Reloading…`,
      );
      window.setTimeout(() => window.location.reload(), 700);
    } catch (resetError) {
      setResetMessage(
        resetError instanceof Error ? resetError.message : "Could not reset projects.",
      );
      setResetting(false);
      setConfirmingReset(null);
    }
  }

  const includeCount = countPatterns(fileRulesDraft.includePatterns);
  const excludeCount = countPatterns(fileRulesDraft.excludePatterns);
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

  const selectedPreset = SKILL_PRESETS.find((preset) => preset.id === selectedSkillKey);
  const selectedCustom = preferences.customSkills.find(
    (skill) => skill.id === selectedSkillKey,
  );

  function addCustomSkill() {
    const name = newSkillName.trim();
    const instructions = newSkillInstructions.trim();
    if (!name || !instructions) {
      return;
    }
    const skill: CustomSkill = {
      id: makeCustomSkillId(),
      name: name.slice(0, 80),
      instructions: instructions.slice(0, 1200),
    };
    onPreferencesChange({
      ...preferences,
      customSkills: [...preferences.customSkills, skill],
    });
    setNewSkillName("");
    setNewSkillInstructions("");
    setSelectedSkillKey(skill.id);
  }

  function updateCustomSkill(id: string, patch: Partial<CustomSkill>) {
    onPreferencesChange({
      ...preferences,
      customSkills: preferences.customSkills.map((skill) =>
        skill.id === id ? { ...skill, ...patch } : skill,
      ),
    });
  }

  function removeCustomSkill(id: string) {
    onPreferencesChange({
      ...preferences,
      customSkills: preferences.customSkills.filter((skill) => skill.id !== id),
    });
    setSelectedSkillKey(SKILL_PRESETS[0].id);
  }

  return (
    <div className="settings-simplified-page">
      <header className="settings-page-header">
        <p className="eyebrow">Settings</p>
        <p>Everyday preferences. Your AI models live in the Models tab.</p>
      </header>

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
          <div className="settings-field">
            <span className="settings-field-label">Text size</span>
            <div className="segmented-control" aria-label="Text size">
              {(["small", "medium", "large"] as const).map((size) => (
                <button
                  key={size}
                  type="button"
                  className={preferences.textSize === size ? "is-selected" : ""}
                  onClick={() => updatePreference({ textSize: size })}
                >
                  {formatLabel(size)}
                </button>
              ))}
            </div>
          </div>
          <label className="settings-developer-toggle">
            <input
              type="checkbox"
              checked={preferences.defaultStreaming}
              onChange={(event) => updatePreference({ defaultStreaming: event.target.checked })}
            />
            <span>
              <strong>Stream answers</strong>
              <small>Show the answer word-by-word as the model writes it. New chats start with this.</small>
            </span>
          </label>
          <label className="settings-developer-toggle">
            <input
              type="checkbox"
              checked={preferences.defaultReasoning}
              onChange={(event) => updatePreference({ defaultReasoning: event.target.checked })}
            />
            <span>
              <strong>Reasoning by default</strong>
              <small>Let thinking-capable models reason before answering (slower, often better). New chats start with this.</small>
            </span>
          </label>
          <label className="settings-developer-toggle">
            <input
              type="checkbox"
              checked={preferences.developerMode}
              onChange={(event) => updatePreference({ developerMode: event.target.checked })}
            />
            <span>
              <strong>Developer mode</strong>
              <small>Show advanced model, file, and integration settings. Off by default for a simpler experience.</small>
            </span>
          </label>
        </article>
      </section>

      {preferences.developerMode ? (
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
      ) : null}

      <section className="panel settings-clean-card">
        <div className="panel-heading compact-heading">
          <div>
            <p className="eyebrow">Skills</p>
            <h3>How answers are written</h3>
            <p className="panel-helper">
              A skill is a short instruction that shapes the tone and focus of answers.
              Edit a built-in one or add your own, then pick a skill per question in Ask
              under “Style” (developer mode).
            </p>
          </div>
        </div>

        <details className="settings-skill-help">
          <summary>What makes a good skill?</summary>
          <div className="settings-skill-help-body">
            <p className="settings-skill-help-label">Good</p>
            <ul>
              <li>Describe the focus: "Prioritise infrastructure and deployment files."</li>
              <li>Set the tone: "Answer in short, plain steps a new teammate can follow."</li>
              <li>Name what matters: "Always mention rollback steps and risks."</li>
            </ul>
            <p className="settings-skill-help-label">Avoid</p>
            <ul>
              <li>Don't ask it to invent facts — it answers from your project's real files.</li>
              <li>Don't paste long essays; a few clear sentences work best.</li>
            </ul>
            <p>Changes only affect how answers are written. They never touch your files.</p>
          </div>
        </details>

        <label className="settings-skill-select">
          <span className="sr-only">Choose a skill</span>
          <select
            value={selectedSkillKey}
            onChange={(event) => setSelectedSkillKey(event.target.value)}
          >
            <optgroup label="Built-in">
              {SKILL_PRESETS.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.name}
                </option>
              ))}
            </optgroup>
            {preferences.customSkills.length > 0 ? (
              <optgroup label="Your skills">
                {preferences.customSkills.map((skill) => (
                  <option key={skill.id} value={skill.id}>
                    {skill.name}
                  </option>
                ))}
              </optgroup>
            ) : null}
            <option value="__new__">+ Create a custom skill…</option>
          </select>
        </label>

        {selectedPreset ? (
          <div className="settings-skill-editor">
            <small className="settings-skill-editor-note">{selectedPreset.purpose}</small>
            <textarea
              rows={4}
              value={skillDrafts[selectedPreset.id] ?? ""}
              placeholder={selectedPreset.defaultInstructions}
              onChange={(event) =>
                setSkillDrafts((current) => ({
                  ...current,
                  [selectedPreset.id]: event.target.value,
                }))
              }
            />
            <div className="settings-clean-actions">
              <button
                className="primary-button"
                type="button"
                disabled={savingSkills}
                onClick={() => void saveSkillGuidance()}
              >
                {savingSkills ? "Saving…" : "Save skill"}
              </button>
            </div>
            <p className="settings-message">{skillMessage}</p>
          </div>
        ) : selectedCustom ? (
          <div className="settings-skill-editor">
            <input
              className="custom-skill-name"
              value={selectedCustom.name}
              maxLength={80}
              placeholder="Skill name"
              onChange={(event) =>
                updateCustomSkill(selectedCustom.id, { name: event.target.value })
              }
            />
            <textarea
              rows={4}
              value={selectedCustom.instructions}
              maxLength={1200}
              placeholder="Instructions — e.g. Answer in short, plain steps; always mention rollback risks."
              onChange={(event) =>
                updateCustomSkill(selectedCustom.id, { instructions: event.target.value })
              }
            />
            <div className="settings-clean-actions">
              <button
                className="secondary-action settings-danger-button"
                type="button"
                onClick={() => removeCustomSkill(selectedCustom.id)}
              >
                Remove skill
              </button>
              <span className="settings-skill-editor-note">Saved automatically.</span>
            </div>
          </div>
        ) : (
          <div className="settings-skill-editor">
            <input
              className="custom-skill-name"
              value={newSkillName}
              maxLength={80}
              placeholder="New skill name (e.g. Security reviewer)"
              onChange={(event) => setNewSkillName(event.target.value)}
            />
            <textarea
              rows={4}
              value={newSkillInstructions}
              maxLength={1200}
              placeholder="What should it focus on? e.g. Flag security risks first, cite CVEs, suggest the safest fix."
              onChange={(event) => setNewSkillInstructions(event.target.value)}
            />
            <div className="settings-clean-actions">
              <button
                className="primary-button"
                type="button"
                disabled={!newSkillName.trim() || !newSkillInstructions.trim()}
                onClick={addCustomSkill}
              >
                Create skill
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="panel settings-clean-card settings-danger-card">
        <div className="panel-heading compact-heading">
          <div>
            <p className="eyebrow">Reset</p>
            <h3>Reset settings or projects</h3>
            <p className="panel-helper">
              Two separate resets. Your actual project files on disk are never touched,
              and installed Ollama models are always left alone.
            </p>
          </div>
        </div>
        <div className="settings-reset-grid">
          <div className="settings-reset-option">
            <div>
              <strong>Reset settings</strong>
              <small>Theme, developer mode, accent, skills, and file rules go back to defaults. Your projects stay.</small>
            </div>
            {confirmingReset === "settings" ? (
              <div className="settings-reset-actions">
                <button className="secondary-action settings-danger-button" type="button" onClick={resetSettings}>
                  Yes, reset settings
                </button>
                <button className="text-button" type="button" onClick={() => setConfirmingReset(null)}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                className="secondary-action"
                type="button"
                disabled={resetting}
                onClick={() => { setResetMessage(null); setConfirmingReset("settings"); }}
              >
                Reset settings
              </button>
            )}
          </div>

          <div className="settings-reset-option">
            <div>
              <strong>Reset projects &amp; data</strong>
              <small>Removes every project and its local search index, returning to the first-run screen. Your settings stay.</small>
            </div>
            {confirmingReset === "workspaces" ? (
              <div className="settings-reset-actions">
                <span className="settings-danger-confirm">Can't be undone.</span>
                <button
                  className="primary-button settings-danger-button"
                  type="button"
                  disabled={resetting}
                  onClick={() => void resetWorkspaces()}
                >
                  {resetting ? "Resetting…" : "Yes, remove projects"}
                </button>
                <button className="text-button" type="button" disabled={resetting} onClick={() => setConfirmingReset(null)}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                className="secondary-action settings-danger-button"
                type="button"
                disabled={resetting}
                onClick={() => { setResetMessage(null); setConfirmingReset("workspaces"); }}
              >
                Reset projects &amp; data
              </button>
            )}
          </div>
        </div>
        {resetMessage ? <p className="settings-message">{resetMessage}</p> : null}
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
