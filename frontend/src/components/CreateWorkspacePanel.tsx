import type { FormEvent } from "react";
import { useState } from "react";

import { createWorkspace } from "../api/client";
import { chooseProjectDirectory, isRunningInsideTauri } from "../desktopRuntime";
import type { CreatedWorkspace, WorkspacePersistence } from "../api/types";

interface CreateWorkspacePanelProps {
  onCreated: (workspace: CreatedWorkspace) => void;
  onCancel: () => void;
}

type AssistantMode =
  | "devops"
  | "developer"
  | "documentation"
  | "support_incident"
  | "manager_summary"
  | "tester"
  | "business_analyst";

const assistantModes: Array<{
  id: AssistantMode;
  label: string;
  description: string;
}> = [
  {
    id: "devops",
    label: "DevOps",
    description: "Infrastructure, CI/CD, Terraform, Kubernetes, and runtime setup.",
  },
  {
    id: "developer",
    label: "Developer",
    description: "Application code, structure, implementation notes, and tests.",
  },
  {
    id: "documentation",
    label: "Documentation",
    description: "READMEs, architecture notes, onboarding, and project summaries.",
  },
  {
    id: "support_incident",
    label: "Support",
    description: "Incidents, troubleshooting notes, logs, and operational questions.",
  },
  {
    id: "manager_summary",
    label: "Manager summary",
    description: "High-level summaries, risks, progress, and stakeholder notes.",
  },
  {
    id: "tester",
    label: "Tester / QA",
    description: "Test coverage, how to run tests, and what to verify.",
  },
  {
    id: "business_analyst",
    label: "Business analyst",
    description: "Plain-language overview, features, and stakeholders — no deep code.",
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
    description: "Remembers everything. The index and your conversations are saved — come back in weeks.",
  },
  {
    id: "temporary",
    label: "Temporary",
    description: "Forgets when you quit. The assistant knows this project only for the current session.",
  },
];

export function CreateWorkspacePanel({ onCreated, onCancel }: CreateWorkspacePanelProps) {
  const [name, setName] = useState("");
  const [projectPath, setProjectPath] = useState("");
  const [assistantMode, setAssistantMode] = useState<AssistantMode>("devops");
  const [persistence, setPersistence] = useState<WorkspacePersistence>("saved");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pickingDirectory, setPickingDirectory] = useState(false);

  const trimmedName = name.trim();
  const trimmedPath = projectPath.trim();
  const canSubmit = trimmedName.length > 0 && trimmedPath.length > 0 && !submitting;

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
        setError("The native folder picker is available in the packaged desktop app. Paste an absolute path here while using the browser dev server.");
      }
    } catch (pickerError) {
      setError(pickerError instanceof Error ? pickerError.message : "Could not open the folder picker.");
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
        privacy_mode: "local_only",
        persistence,
      });
      onCreated(workspace);
    } catch (createError) {
      setError(
        createError instanceof Error ? createError.message : "Could not create the workspace.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="create-workspace-page">
      <header className="create-workspace-intro">
        <span className="section-eyebrow">New workspace</span>
        <h1>Create a local workspace</h1>
        <p>Point the app at a project folder. Everything — scan, context, and answers — stays on your machine.</p>
      </header>

      <form className="create-workspace-form surface-panel" onSubmit={handleSubmit}>
        <div className="create-field-block">
          <label className="create-field" htmlFor="workspace-name">
            <span className="create-field-label">Workspace name</span>
            <input
              id="workspace-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Brand site"
              autoFocus
            />
          </label>

          <label className="create-field" htmlFor="workspace-path">
            <span className="create-field-label">Project folder</span>
            <div className="path-picker-row">
              <input
                id="workspace-path"
                value={projectPath}
                onChange={(event) => setProjectPath(event.target.value)}
                placeholder="/Users/you/Documents/my-project"
              />
              <button
                className="secondary-action"
                type="button"
                onClick={() => void handleChooseDirectory()}
                disabled={pickingDirectory}
              >
                {pickingDirectory ? "Opening…" : "Choose folder"}
              </button>
            </div>
            <small>The path is sent only to your local backend.</small>
          </label>
        </div>

        <div className="create-mode-section">
          <div className="create-section-head">
            <span className="section-eyebrow">Assistant mode</span>
            <p>Sets the starting lens — guidance and wording only. It never runs anything.</p>
          </div>
          <div className="choice-card-grid compact assistant-grid">
            {assistantModes.map((mode) => (
              <button
                key={mode.id}
                type="button"
                className={`choice-card assistant-card${assistantMode === mode.id ? " is-selected" : ""}`}
                onClick={() => setAssistantMode(mode.id)}
              >
                <strong>{mode.label}</strong>
                <span>{mode.description}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="create-mode-section">
          <div className="create-section-head">
            <span className="section-eyebrow">Project memory</span>
            <p>Is this project kept between sessions? You can promote a temporary project to permanent anytime.</p>
          </div>
          <div className="choice-card-grid compact">
            {persistenceModes.map((mode) => (
              <button
                key={mode.id}
                type="button"
                className={`choice-card${persistence === mode.id ? " is-selected" : ""}${mode.id === "temporary" ? " is-temporary" : ""}`}
                onClick={() => setPersistence(mode.id)}
              >
                <span className="choice-card-title">
                  <strong>{mode.label}</strong>
                  {mode.id === "temporary" ? (
                    <span className="choice-card-tag">forgets on quit</span>
                  ) : null}
                </span>
                <span>{mode.description}</span>
              </button>
            ))}
          </div>
        </div>

        {error ? <p className="settings-message error">{error}</p> : null}

        <div className="create-form-actions">
          <button className="primary-action" type="submit" disabled={!canSubmit}>
            {submitting ? "Creating…" : "Create workspace"}
          </button>
          <button className="secondary-action" type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
