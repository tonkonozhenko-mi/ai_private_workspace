import { useEffect, useMemo, useState } from "react";

import type {
  WorkspaceUIAction,
  WorkspaceUIActionCatalog,
} from "../api/types";
import { CopyButton } from "./CopyButton";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

interface UIActionsPanelProps {
  catalog: WorkspaceUIActionCatalog;
}

export function UIActionsPanel({ catalog }: UIActionsPanelProps) {
  const groups = useMemo(() => groupActions(catalog), [catalog]);
  const defaultAction = getDefaultAction(catalog);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(
    defaultAction?.id ?? null,
  );

  useEffect(() => {
    setSelectedActionId(getDefaultAction(catalog)?.id ?? null);
  }, [catalog]);

  const selectedAction =
    catalog.actions.find((action) => action.id === selectedActionId) ??
    defaultAction;

  return (
    <section className="action-catalog native-action-catalog">
      <div className="panel action-catalog-panel native-action-panel">
        <div className="panel-heading action-catalog-heading">
          <div>
            <p className="eyebrow">Capabilities</p>
            <h2>What this workspace can do</h2>
            <p className="panel-intro action-catalog-subtitle">
              A transparent list of what the assistant can do, grouped by purpose. Nothing runs from this page.
            </p>
          </div>
          <span className="panel-count">{catalog.actions.length}</span>
        </div>

        {catalog.actions.length > 0 ? (
          <div className="action-groups native-action-groups">
            {groups.map(([category, actions]) => {
              const summary = getCategorySummary(category);
              return (
                <section className="action-group native-action-group" key={category}>
                  <div className="action-group-heading">
                    <div>
                      <h3>{summary.title}</h3>
                      <p>{summary.description}</p>
                    </div>
                    <StatusBadge label={`${actions.length} capabilities`} tone="neutral" />
                  </div>

                  <div className="action-card-list">
                    {actions.map((action) => (
                      <button
                        aria-pressed={selectedAction?.id === action.id}
                        className={`action-card${
                          action.is_primary ? " is-primary" : ""
                        }${selectedAction?.id === action.id ? " is-selected" : ""}`}
                        key={action.id}
                        type="button"
                        onClick={() => setSelectedActionId(action.id)}
                      >
                        <div className="action-card-topline">
                          <span className="action-card-icon" aria-hidden="true">
                            {summary.icon}
                          </span>
                          <strong>{formatCapabilityText(action.title)}</strong>
                        </div>
                        <p>{formatCapabilityText(action.description)}</p>
                        <div className="action-card-badges">
                          <StatusBadge label={action.status} />
                          {action.is_primary ? (
                            <StatusBadge label="Recommended" />
                          ) : null}
                          <StatusBadge
                            label={getMutationBadge(action).label}
                            tone={getMutationBadge(action).tone}
                          />
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="No capabilities are available"
            message="The backend did not return any capabilities for this workspace."
            compact
          />
        )}
      </div>

      {selectedAction ? <ActionInspector action={selectedAction} /> : null}
    </section>
  );
}

function ActionInspector({ action }: { action: WorkspaceUIAction }) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    setShowAdvanced(false);
  }, [action.id]);

  return (
    <aside className="panel action-details-panel native-action-inspector" aria-live="polite">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Inspector</p>
          <h2>{formatCapabilityText(action.title)}</h2>
        </div>
        <StatusBadge label={action.status} size="md" />
      </div>

      <p className="action-details-description">{formatCapabilityText(action.description)}</p>

      <div
        className={`action-safety-card${
          action.mutates_data ? " is-warning" : " is-readonly"
        }`}
      >
        <StatusBadge
          label={getMutationBadge(action).label}
          tone={getMutationBadge(action).tone}
        />
        <div>
          <strong>{getMutationCopy(action).title}</strong>
          <p>{getMutationCopy(action).description}</p>
        </div>
      </div>

      <dl className="action-details-list native-action-details-list">
        <DetailRow label="Purpose" value={formatLabel(action.category)} />
        <DetailRow label="Primary action" value={action.is_primary ? "Yes" : "No"} />
        <DetailRow label="Reason" value={formatCapabilityText(action.reason)} />
      </dl>

      <button
        className="secondary-button action-advanced-toggle"
        type="button"
        aria-expanded={showAdvanced}
        onClick={() => setShowAdvanced((value) => !value)}
      >
        {showAdvanced ? "Hide technical details" : "Show technical details"}
      </button>

      {showAdvanced ? (
        <div className="action-advanced-panel">
          <dl className="action-details-list native-action-details-list">
            <DetailRow label="HTTP method" value={action.method} mono />
            <DetailRow label="Endpoint" value={action.endpoint} mono />
          </dl>

          <div className="action-endpoint native-action-endpoint">
            <span>Copy technical endpoint</span>
            <div>
              <code title={action.endpoint} tabIndex={0}>
                {action.endpoint}
              </code>
              <CopyButton text={action.endpoint} label="endpoint" />
            </div>
          </div>
        </div>
      ) : null}
    </aside>
  );
}

function getMutationBadge(action: WorkspaceUIAction): {
  label: string;
  tone: "warning" | "info" | "neutral";
} {
  if (!action.mutates_data) {
    return { label: "Read-only", tone: "neutral" };
  }

  if (action.category.toLowerCase() === "ask") {
    return { label: "Records Activity", tone: "info" };
  }

  if (action.category.toLowerCase() === "setup") {
    return { label: "Updates Context", tone: "warning" };
  }

  return { label: "Updates Workspace", tone: "warning" };
}

function getMutationCopy(action: WorkspaceUIAction): {
  title: string;
  description: string;
} {
  if (!action.mutates_data) {
    return {
      title: "Safe to inspect",
      description:
        "This capability does not change workspace data. It is shown here so you can understand the available workflow.",
    };
  }

  if (action.category.toLowerCase() === "ask") {
    return {
      title: "Records workspace activity",
      description:
        "Asking can save an activity event and answer metadata. This capabilities view still does not run the request; use the Ask tab for explicit submission.",
    };
  }

  if (action.category.toLowerCase() === "setup") {
    return {
      title: "Updates workspace context",
      description:
        "Scan and index capabilities can update workspace metadata or searchable context when used from an explicit flow. This capabilities view only explains the workflow.",
    };
  }

  return {
    title: "May update workspace data",
    description:
      "This capability can change workspace state when used from an explicit workflow. This capabilities view remains inspection-only.",
  };
}

function formatCapabilityText(value: string) {
  return value
    .replace(/Ask using selected LLM/gi, "Ask with chosen AI model")
    .replace(/Asked with selected LLM/gi, "Asked with chosen AI model")
    .replace(/using selected LLM/gi, "with chosen AI model")
    .replace(/selected LLM/gi, "chosen AI model")
    .replace(/LLM/gi, "AI model");
}

function DetailRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? "is-mono" : ""}>{value}</dd>
    </div>
  );
}

function getDefaultAction(catalog: WorkspaceUIActionCatalog) {
  return (
    catalog.actions.find((action) => action.id === catalog.primary_action_id) ??
    catalog.actions.find((action) => action.is_primary) ??
    catalog.actions[0] ??
    null
  );
}

function groupActions(catalog: WorkspaceUIActionCatalog) {
  const groups = new Map<string, WorkspaceUIActionCatalog["actions"]>();
  for (const action of catalog.actions) {
    const group = groups.get(action.category) ?? [];
    group.push(action);
    groups.set(action.category, group);
  }
  return Array.from(groups.entries());
}

function getCategorySummary(category: string) {
  const normalized = category.toLowerCase();
  const summaries: Record<
    string,
    { title: string; description: string; icon: string }
  > = {
    setup: {
      title: "Setup",
      description: "Prepare scan and index state before deeper workspace analysis.",
      icon: "1",
    },
    ask: {
      title: "Ask",
      description: "Use indexed context to answer workspace questions.",
      icon: "2",
    },
    models: {
      title: "Models",
      description: "Review local AI readiness, selections, and experiment guidance.",
      icon: "3",
    },
    project: {
      title: "Project",
      description: "Generate read-only project reports and summaries.",
      icon: "4",
    },
    timeline: {
      title: "Activity",
      description: "Review workspace history and persisted activity.",
      icon: "5",
    },
  };

  return (
    summaries[normalized] ?? {
      title: formatLabel(category),
      description: "Review workspace capability metadata returned by the backend.",
      icon: "•",
    }
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
