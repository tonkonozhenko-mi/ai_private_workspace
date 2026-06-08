import type { WorkspaceUIActionCatalog } from "../api/types";

interface UIActionsPanelProps {
  catalog: WorkspaceUIActionCatalog;
}

export function UIActionsPanel({ catalog }: UIActionsPanelProps) {
  const groups = groupActions(catalog);

  return (
    <section className="panel action-catalog-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Read-only catalog</p>
          <h2>Available UI actions</h2>
        </div>
        <span className="panel-count">{catalog.actions.length}</span>
      </div>

      <p className="panel-intro">
        These routes are displayed for inspection only. This prototype never
        invokes workspace actions.
      </p>

      <div className="action-groups">
        {groups.map(([category, actions]) => (
          <section className="action-group" key={category}>
            <h3>{formatLabel(category)}</h3>
            <div className="action-list">
              {actions.map((action) => (
                <article
                  className={`action-row${action.is_primary ? " is-primary" : ""}`}
                  key={action.id}
                >
                  <div className="action-row-main">
                    <div className="action-title-line">
                      <strong>{action.title}</strong>
                      <span className={`status-badge status-${action.status}`}>
                        {formatLabel(action.status)}
                      </span>
                      {action.mutates_data ? (
                        <span className="mutation-badge">writes data</span>
                      ) : null}
                    </div>
                    <p>{action.description}</p>
                    <span className="action-reason">{action.reason}</span>
                  </div>
                  <code>
                    <span>{action.method}</span> {action.endpoint}
                  </code>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
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
