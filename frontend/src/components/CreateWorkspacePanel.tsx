import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { createWorkspace } from "../api/client";
import type { CreatedWorkspace } from "../api/types";

interface CreateWorkspacePanelProps {
  onCreated: (workspace: CreatedWorkspace) => void;
  onCancel: () => void;
}

type AssistantMode = "devops" | "developer" | "documentation" | "support" | "manager_summary";
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
    id: "support",
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
          <span className="section-eyebrow">Workspace onboarding</span>
          <h1>Add a local project</h1>
          <p>
            Create a workspace from a local folder path. Scanning and search-context
            building stay explicit, so the next steps are easy to review.
          </p>
        </div>
        <span className="status-pill info">Manual setup</span>
      </section>

      <section className="create-workspace-grid">
        <form className="create-workspace-form surface-panel" onSubmit={handleSubmit}>
          <div className="panel-heading">
            <div>
              <span className="section-eyebrow">Project details</span>
              <h2>Create workspace</h2>
            </div>
            <span className="status-pill">Local backend</span>
          </div>

          <label className="settings-field-row create-field-row">
            <span>Workspace name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Example: CIF MSK Debezium"
            />
          </label>

          <label className="settings-field-row create-field-row">
            <span>Local project path</span>
            <input
              value={projectPath}
              onChange={(event) => setProjectPath(event.target.value)}
              placeholder="/Users/maks/Documents/my-project"
            />
          </label>

          <div className="create-mode-section">
            <div>
              <span className="section-eyebrow">Assistant mode</span>
              <p>Choose the starting lens. You can refine skills later.</p>
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
              <p>Keep the first version predictable and local-first.</p>
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
          <h2>Clear first run path</h2>
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
          </div>
        </aside>
      </section>
    </div>
  );
}
