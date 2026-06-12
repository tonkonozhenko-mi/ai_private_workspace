import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { createWorkspace } from "../api/client";
import type { CreatedWorkspace } from "../api/types";

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
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmedName = name.trim();
  const trimmedPath = projectPath.trim();
  const canSubmit = trimmedName.length > 0 && trimmedPath.length > 0 && !submitting;
  const selectedMode = useMemo(
    () => assistantModes.find((mode) => mode.id === assistantMode),
    [assistantMode],
  );

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
      <section className="create-workspace-hero surface-panel">
        <div>
          <span className="section-eyebrow">Project onboarding</span>
          <h1>Add a local project</h1>
          <p>
            Point AI Private Workspace at a local folder, choose how you want to
            work with it, and then review each setup step before anything runs.
          </p>
        </div>
        <div className="create-hero-card" aria-label="Onboarding flow preview">
          <span>Project</span>
          <span>Skills</span>
          <span>Context</span>
          <strong>Ask</strong>
        </div>
      </section>

      <section className="create-workspace-grid">
        <form className="create-workspace-form surface-panel" onSubmit={handleSubmit}>
          <div className="panel-heading">
            <div>
              <span className="section-eyebrow">Project details</span>
              <h2>Create workspace</h2>
              <p className="panel-helper">Start with a name and the absolute path to a local project folder.</p>
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
            <input
              value={projectPath}
              onChange={(event) => setProjectPath(event.target.value)}
              placeholder="/Users/maks/Documents/my-project"
            />
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

        <aside className="create-workspace-guide surface-panel">
          <span className="section-eyebrow">What happens next</span>
          <h2>First run path</h2>
          <p>Follow this simple path after the workspace is created.</p>
          <ol className="onboarding-step-list">
            <li>
              <strong>Create workspace</strong>
              <span>Save the name, local path, assistant mode, and privacy mode.</span>
            </li>
            <li>
              <strong>Scan project</strong>
              <span>Review detected technologies before building searchable context.</span>
            </li>
            <li>
              <strong>Build search context</strong>
              <span>Prepare source-backed answers from the scanned local files.</span>
            </li>
            <li>
              <strong>Ask a question</strong>
              <span>Use local project context with visible sources.</span>
            </li>
          </ol>
          <div className="safety-note-card">
            <strong>Safe by default</strong>
            <span>
              The frontend sends this form to your local backend. It does not run
              shell commands, scan files, rebuild context, or call models automatically.
            </span>
          </div>
          <div className="selected-mode-preview">
            <span>Selected mode</span>
            <strong>{selectedMode?.label ?? "DevOps mode"}</strong>
            <small>{selectedMode?.description ?? "Infrastructure, CI/CD, Terraform, Kubernetes, and runtime setup."}</small>
          </div>
        </aside>
      </section>
    </div>
  );
}
