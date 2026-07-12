import type { FormEvent } from "react";
import { useState } from "react";

import { createWorkspace } from "../api/client";
import { chooseProjectDirectory, isRunningInsideTauri } from "../desktopRuntime";
import type { CreatedWorkspace, WorkspacePersistence } from "../api/types";

interface CreateWorkspacePanelProps {
  onCreated: (workspace: CreatedWorkspace) => void;
  onCancel: () => void;
}

// Who is reading this project? The same facts, ordered and worded for the person
// in front of them — the ids match the backend's lenses exactly. Nothing is
// preselected: a silent default would quietly make every user a DevOps engineer,
// and no choice is honest ("just exploring") rather than wrong.
const assistantModes: Array<{ id: string; label: string; description: string }> = [
  {
    id: "developer",
    label: "Developer",
    description: "Architecture, modules, key code paths and tests.",
  },
  {
    id: "devops",
    label: "DevOps",
    description: "Deployment, environments, CI/CD, and what can break in production.",
  },
  {
    id: "tester",
    label: "Tester / QA",
    description: "What's risky to change, how tests run, where coverage is thin.",
  },
  {
    id: "manager",
    label: "Manager",
    description: "What changed, what's risky, how ready this is — in plain language.",
  },
  {
    id: "business_analyst",
    label: "Business analyst",
    description: "What the system does for its users, features, and stakeholders.",
  },
  {
    id: "dba",
    label: "DBA",
    description: "Tables and relationships, migrations, indexes, and what bites at scale.",
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
  const [persistence, setPersistence] = useState<WorkspacePersistence>("saved");
  // "" = not chosen. Everything downstream reads that as the neutral developer
  // lens, so a person who just wants to look around loses nothing.
  const [assistantMode, setAssistantMode] = useState<string>("");
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
            <span className="section-eyebrow">Who are you on this project?</span>
            <p>
              Sets the lens: what the project leads with and how answers are worded. It never
              changes which files are searched or what is true — and you can switch it any time.
            </p>
          </div>
          <div className="choice-card-grid compact assistant-grid">
            {assistantModes.map((mode) => (
              <button
                key={mode.id}
                type="button"
                className={`choice-card assistant-card${assistantMode === mode.id ? " is-selected" : ""}`}
                onClick={() =>
                  // Clicking the selected card again clears it — "just exploring".
                  setAssistantMode((current) => (current === mode.id ? "" : mode.id))
                }
              >
                <strong>{mode.label}</strong>
                <span>{mode.description}</span>
              </button>
            ))}
          </div>
          <small>Just exploring? Leave this unset — you'll get the neutral developer view.</small>
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
