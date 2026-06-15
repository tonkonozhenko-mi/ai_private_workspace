import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { createWorkspace } from "../api/client";
import { chooseProjectDirectory, isRunningInsideTauri } from "../desktopRuntime";
import type { CreatedWorkspace, WorkspacePersistence } from "../api/types";

interface CreateWorkspacePanelProps {
  onCreated: (workspace: CreatedWorkspace) => void;
  onCancel: () => void;
}

type AssistantMode = "devops" | "developer" | "documentation" | "support_incident" | "manager_summary";
type PrivacyMode = "local_only" | "manual_network";

const assistantModes: Array<{
  id: AssistantMode;
  label: string;
  description: string;
}> = [
  {
    id: "devops",
    label: "DevOps mode",
    description: "Infrastructure, CI/CD, Terraform, Kubernetes, and runtime setup.",
  },
  {
    id: "developer",
    label: "Developer mode",
    description: "Application code, structure, implementation notes, and tests.",
  },
  {
    id: "documentation",
    label: "Documentation mode",
    description: "README files, architecture notes, onboarding, and project summaries.",
  },
  {
    id: "support_incident",
    label: "Support mode",
    description: "Incidents, troubleshooting notes, logs, and operational questions.",
  },
  {
    id: "manager_summary",
    label: "Manager summary mode",
    description: "High-level summaries, risks, progress, and stakeholder-friendly notes.",
  },
];

const persistenceModes: Array<{
  id: WorkspacePersistence;
  label: string;
  description: string;
}> = [
  {
    id: "saved",
    label: "Permanent",
    description: "Remembers everything. The index and your conversations are saved — come back to it in weeks.",
  },
  {
    id: "temporary",
    label: "Temporary",
    description: "Forgets when you quit. The assistant knows this project only for the current session.",
  },
];

const privacyModes: Array<{
  id: PrivacyMode;
  label: string;
  description: string;
}> = [
  {
    id: "local_only",
    label: "Local only",
    description: "Keep work local. The frontend never executes shell commands.",
  },
  {
    id: "manual_network",
    label: "Manual network later",
    description: "Reserved for future explicit, user-approved network flows.",
  },
];

export function CreateWorkspacePanel({ onCreated, onCancel }: CreateWorkspacePanelProps) {
  const [name, setName] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [assistantMode, setAssistantMode] = useState<AssistantMode>("devops");
  const [privacyMode, setPrivacyMode] = useState<PrivacyMode>("local_only");
  const [persistence, setPersistence] = useState<WorkspacePersistence>("saved");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickingDirectory, setPickingDirectory] = useState(false);

  const trimmedName = name.trim();
  const trimmedPath = projectPath.trim();
  const canSubmit = trimmedName.length > 0 && trimmedPath.length > 0 && !submitting;
  const selectedMode = useMemo(
    () => assistantModes.find((mode) => mode.id === assistantMode),
    [assistantMode],
  );

  async function handleChooseDirectory() {
    setPickingDirectory(true);
    setError(null);
    try {
      const selectedPath = await chooseProjectDirectory();
      if (selectedPath) {
        setProjectPath(selectedPath);
        if (!name.trim()) {
          const suggestedName = selectedPath.split("/").filter(Boolean).pop();
          if (suggestedName) {
            setName(suggestedName);
          }
        }
      } else if (!isRunningInsideTauri()) {
        setError("Native folder picker is available in the packaged desktop app. Paste the path here while using the browser dev server.");
      }
    } catch (pickerError) {
      setError(pickerError instanceof Error ? pickerError.message : "Could not open folder picker.");
    } finally {
      setPickingDirectory(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const workspace = await createWorkspace({
        name: trimmedName,
        project_path: trimmedPath,
        assistant_mode: assistantMode,
        privacy_mode: privacyMode,
        persistence,
      });
      onCreated(workspace);
    } catch (createError) {
      setError(
        createError instanceof Error
          ? createError.message
          : "Could not create workspace.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="create-workspace-page">
      <section className="create-workspace-hero surface-panel create-workspace-hero-simple">
        <div>
          <span className="section-eyebrow">New workspace</span>
          <h1>Choose a local project.</h1>
          <p>
            Pick a folder, create the workspace, then use the Overview buttons to scan, build context, and ask.
          </p>
        </div>
        <button className="primary-action" type="button" onClick={() => void handleChooseDirectory()} disabled={pickingDirectory}>
          {pickingDirectory ? "Opening Finder…" : "Choose folder"}
        </button>
      </section>

      <section className="create-workspace-grid create-workspace-grid-simple">
        <form className="create-workspace-form surface-panel" onSubmit={handleSubmit}>
          <div className="panel-heading">
            <div>
              <span className="section-eyebrow">Project details</span>
              <h2>Create workspace</h2>
              <p className="panel-helper">Use Choose folder in the packaged app, or paste an absolute path in dev mode.</p>
            </div>
            <span className="status-pill">Local backend</span>
          </div>

          <label className="settings-field-row create-field-row">
            <span>Workspace name</span>
            <small>Use a clear name you will recognize in the sidebar.</small>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Example: CIF MSK Debezium"
            />
          </label>

          <label className="settings-field-row create-field-row">
            <span>Local project path</span>
            <small>The path is sent only to your local backend.</small>
            <div className="path-picker-row">
              <input
                value={projectPath}
                onChange={(event) => setProjectPath(event.target.value)}
                placeholder="/Users/maks/Documents/my-project"
              />
              <button className="secondary-action" type="button" onClick={() => void handleChooseDirectory()} disabled={pickingDirectory}>
                {pickingDirectory ? "Opening…" : "Browse"}
              </button>
            </div>
          </label>

          <div className="create-mode-section">
            <div>
              <span className="section-eyebrow">Assistant mode</span>
              <p>Choose the starting lens. It only changes guidance and wording; it does not run anything.</p>
            </div>
            <div className="choice-card-grid">
              {assistantModes.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  className={`choice-card${assistantMode === mode.id ? " is-selected" : ""}`}
                  onClick={() => setAssistantMode(mode.id)}
                >
                  <strong>{mode.label}</strong>
                  <span>{mode.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="create-mode-section">
            <div>
              <span className="section-eyebrow">Privacy mode</span>
              <p>Keep setup predictable. Network-capable flows can be added later with explicit approval.</p>
            </div>
            <div className="choice-card-grid compact">
              {privacyModes.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  className={`choice-card${privacyMode === mode.id ? " is-selected" : ""}`}
                  onClick={() => setPrivacyMode(mode.id)}
                >
                  <strong>{mode.label}</strong>
                  <span>{mode.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="create-mode-section">
            <div>
              <span className="section-eyebrow">Project memory</span>
              <p>Decide whether this project is kept between sessions. You can always promote a temporary project to permanent later.</p>
            </div>
            <div className="choice-card-grid compact">
              {persistenceModes.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  className={`choice-card${persistence === mode.id ? " is-selected" : ""}${mode.id === "temporary" ? " is-temporary" : ""}`}
                  onClick={() => setPersistence(mode.id)}
                >
                  <strong>{mode.label}</strong>
                  <span>{mode.description}</span>
                </button>
              ))}
            </div>
          </div>

          {error ? <p className="settings-message error">{error}</p> : null}

          <div className="create-form-actions">
            <button className="primary-action" type="submit" disabled={!canSubmit}>
              {submitting ? "Creating..." : "Create workspace"}
            </button>
            <button className="secondary-action" type="button" onClick={onCancel}>
              Cancel
            </button>
          </div>
        </form>

        <aside className="create-workspace-guide surface-panel create-workspace-guide-simple">
          <span className="section-eyebrow">Next</span>
          <h2>Three clicks after create</h2>
          <ol className="onboarding-step-list compact-list">
            <li><strong>Scan</strong><span>Detect local files and technologies.</span></li>
            <li><strong>Build context</strong><span>Create searchable local sources.</span></li>
            <li><strong>Ask</strong><span>Chat with saved history and sources.</span></li>
          </ol>
          <div className="selected-mode-preview">
            <span>Selected mode</span>
            <strong>{selectedMode?.label ?? "DevOps mode"}</strong>
          </div>
        </aside>
      </section>
    </div>
  );
}
