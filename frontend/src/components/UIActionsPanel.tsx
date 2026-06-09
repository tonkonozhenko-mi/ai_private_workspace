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
            <p className="eyebrow">Read-only workspace controls</p>
            <h2>Choose what to inspect</h2>
            <p className="panel-intro action-catalog-subtitle">
              Actions are grouped by purpose. The frontend shows safety posture
              and API contracts, but does not run workspace actions from this view.
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
                    <StatusBadge label={`${actions.length} actions`} tone="neutral" />
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
                          <strong>{action.title}</strong>
                        </div>
                        <p>{action.description}</p>
                        <div className="action-card-badges">
                          <StatusBadge label={action.status} />
                          {action.is_primary ? (
                            <StatusBadge label="Recommended" />
                          ) : null}
                          {action.mutates_data ? (
                            <StatusBadge label="Writes Data" />
                          ) : (
                            <StatusBadge label="Read-only" />
                          )}
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
            title="No UI actions are available"
            message="The backend did not return any actions for this workspace."
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
          <h2>{action.title}</h2>
        </div>
        <StatusBadge label={action.status} size="md" />
      </div>

      <p className="action-details-description">{action.description}</p>

      <div
        className={`action-safety-card${
          action.mutates_data ? " is-warning" : " is-readonly"
        }`}
      >
        <StatusBadge label={action.mutates_data ? "Writes Data" : "Read-only"} />
        <div>
          <strong>
            {action.mutates_data ? "Changes workspace state" : "Safe to inspect"}
          </strong>
          <p>
            {action.mutates_data
              ? "This action may change workspace state. This frontend still shows it for review only and does not execute it from the catalog."
              : "This action does not mutate workspace data. It is shown here so you can understand the available workflow."}
          </p>
        </div>
      </div>

      <dl className="action-details-list native-action-details-list">
        <DetailRow label="Purpose" value={formatLabel(action.category)} />
        <DetailRow label="Primary action" value={action.is_primary ? "Yes" : "No"} />
        <DetailRow label="Reason" value={action.reason} />
      </dl>

      <button
        className="secondary-button action-advanced-toggle"
        type="button"
        aria-expanded={showAdvanced}
        onClick={() => setShowAdvanced((value) => !value)}
      >
        {showAdvanced ? "Hide API details" : "Show API details"}
      </button>

      {showAdvanced ? (
        <div className="action-advanced-panel">
          <dl className="action-details-list native-action-details-list">
            <DetailRow label="Method" value={action.method} mono />
            <DetailRow label="Endpoint" value={action.endpoint} mono />
          </dl>

          <div className="action-endpoint native-action-endpoint">
            <span>Copy API endpoint</span>
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
      description: "Inspect workspace capability metadata returned by the backend.",
      icon: "•",
    }
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
