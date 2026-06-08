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
    <section className="action-catalog">
      <div className="panel action-catalog-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Read-only catalog</p>
            <h2>Available UI actions</h2>
          </div>
          <span className="panel-count">{catalog.actions.length}</span>
        </div>

        <p className="panel-intro">
          Select an action to inspect its API contract and safety posture. This
          frontend never invokes workspace actions.
        </p>

        {catalog.actions.length > 0 ? (
          <div className="action-groups">
            {groups.map(([category, actions]) => (
              <section className="action-group" key={category}>
                <h3>{formatLabel(category)}</h3>
                <div className="action-list">
                  {actions.map((action) => (
                    <button
                      aria-pressed={selectedAction?.id === action.id}
                      className={`action-row${
                        action.is_primary ? " is-primary" : ""
                      }${selectedAction?.id === action.id ? " is-selected" : ""}`}
                      key={action.id}
                      type="button"
                      onClick={() => setSelectedActionId(action.id)}
                    >
                      <div className="action-row-main">
                        <div className="action-title-line">
                          <strong>{action.title}</strong>
                          <StatusBadge label={action.status} />
                          {action.mutates_data ? (
                            <StatusBadge label="Writes Data" />
                          ) : null}
                        </div>
                        <p>{action.description}</p>
                      </div>
                      <code>
                        <span>{action.method}</span> {action.endpoint}
                      </code>
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No UI actions are available"
            message="The backend did not return any actions for this workspace."
            compact
          />
        )}
      </div>

      {selectedAction ? <ActionDetails action={selectedAction} /> : null}
    </section>
  );
}

function ActionDetails({ action }: { action: WorkspaceUIAction }) {
  return (
    <aside className="panel action-details-panel" aria-live="polite">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Action details</p>
          <h2>{action.title}</h2>
        </div>
        <StatusBadge label={action.status} size="md" />
      </div>

      <p className="action-details-description">{action.description}</p>

      <dl className="action-details-list">
        <DetailRow label="Method" value={action.method} mono />
        <DetailRow label="Category" value={formatLabel(action.category)} />
        <DetailRow label="Status" value={formatLabel(action.status)} />
        <DetailRow label="Primary action" value={action.is_primary ? "Yes" : "No"} />
        <DetailRow
          label="Mutates data"
          value={action.mutates_data ? "Yes" : "No"}
        />
        <DetailRow label="Reason" value={action.reason} />
      </dl>

      <div className="action-endpoint">
        <span>Endpoint</span>
        <div>
          <code title={action.endpoint} tabIndex={0}>
            {action.endpoint}
          </code>
          <CopyButton text={action.endpoint} label="endpoint" />
        </div>
      </div>

      <p
        className={`action-safety-note${
          action.mutates_data ? " is-warning" : " is-readonly"
        }`}
      >
        {action.mutates_data
          ? "This action may change workspace state. The current frontend does not execute it."
          : "This action is read-only. The current frontend still displays it for inspection only."}
      </p>
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

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}
