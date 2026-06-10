import { useEffect, useMemo, useState } from "react";

import { generateWorkspaceReport, getWorkspaceReportCatalog } from "../api/client";
import type { ReportCatalog, ReportTemplate, WorkspaceReport } from "../api/types";
import { CopyButton } from "./CopyButton";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";

interface ReportsPanelProps {
  workspaceId: string;
  hasScan: boolean;
}

export function ReportsPanel({ workspaceId, hasScan }: ReportsPanelProps) {
  const [catalog, setCatalog] = useState<ReportCatalog | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [report, setReport] = useState<WorkspaceReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCatalogLoading(true);
    setCatalogError(null);
    setReport(null);
    getWorkspaceReportCatalog(workspaceId)
      .then((nextCatalog) => {
        if (cancelled) return;
        setCatalog(nextCatalog);
        setSelectedTemplateId(nextCatalog.templates[0]?.id ?? null);
      })
      .catch((error: unknown) => {
        if (!cancelled) setCatalogError(errorMessage(error));
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const selectedTemplate = useMemo(
    () => catalog?.templates.find((template) => template.id === selectedTemplateId) ?? catalog?.templates[0] ?? null,
    [catalog, selectedTemplateId],
  );

  async function handleGenerate(template: ReportTemplate) {
    setReportLoading(true);
    setReportError(null);
    try {
      const nextReport = await generateWorkspaceReport(workspaceId, template.id);
      setReport(nextReport);
    } catch (error) {
      setReportError(errorMessage(error));
    } finally {
      setReportLoading(false);
    }
  }

  if (catalogLoading) {
    return <LoadingState title="Loading report templates" message="Preparing local-first documentation generators." />;
  }

  if (catalogError) {
    return <ErrorState title="Report templates are unavailable" message={catalogError} compact />;
  }

  if (!catalog || catalog.templates.length === 0) {
    return <EmptyState title="No report templates" message="The backend did not return report templates for this workspace." />;
  }

  return (
    <section className="reports-workbench">
      <div className="panel reports-hero">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Documentation generation</p>
            <h2>Project reports</h2>
            <p className="panel-intro">
              Generate read-only drafts from local scan results, deterministic analysis, saved notes, and conversation metadata.
            </p>
          </div>
          <StatusBadge label={hasScan ? "Scan ready" : "Scan required"} tone={hasScan ? "neutral" : "warning"} />
        </div>
        <div className="report-safety-grid">
          {catalog.safety_notes.map((note) => (
            <div className="report-safety-card" key={note}>{note}</div>
          ))}
        </div>
      </div>

      <div className="reports-layout">
        <div className="panel report-template-panel">
          <div className="panel-heading compact-heading">
            <div>
              <p className="eyebrow">Templates</p>
              <h3>Choose report type</h3>
            </div>
            <span className="panel-count">{catalog.templates.length}</span>
          </div>
          <div className="report-template-list">
            {catalog.templates.map((template) => (
              <button
                key={template.id}
                type="button"
                className={`report-template-card${selectedTemplate?.id === template.id ? " is-selected" : ""}`}
                onClick={() => setSelectedTemplateId(template.id)}
              >
                <strong>{template.title}</strong>
                <span>{template.description}</span>
                <small>{template.best_for}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="panel report-generator-panel">
          {selectedTemplate ? (
            <>
              <div className="panel-heading compact-heading">
                <div>
                  <p className="eyebrow">Selected template</p>
                  <h3>{selectedTemplate.title}</h3>
                </div>
                <StatusBadge label="Read-only" />
              </div>
              <p className="panel-intro">{selectedTemplate.description}</p>
              <dl className="report-template-details">
                <div><dt>Best for</dt><dd>{selectedTemplate.best_for}</dd></div>
                <div><dt>Sources</dt><dd>{selectedTemplate.source_strategy}</dd></div>
                <div><dt>Output</dt><dd>{selectedTemplate.output_style}</dd></div>
              </dl>
              <div className="report-action-row">
                <button
                  className="primary-action"
                  type="button"
                  disabled={reportLoading || !hasScan}
                  onClick={() => handleGenerate(selectedTemplate)}
                >
                  {reportLoading ? "Generating…" : "Generate report draft"}
                </button>
                {!hasScan ? <span className="form-help">Run a project scan first. Reports do not trigger scan automatically.</span> : null}
              </div>
            </>
          ) : null}

          {reportError ? <ErrorState title="Report generation failed" message={reportError} compact /> : null}
        </div>
      </div>

      {report ? <ReportPreview report={report} /> : null}
    </section>
  );
}

function ReportPreview({ report }: { report: WorkspaceReport }) {
  const [showMarkdown, setShowMarkdown] = useState(false);
  return (
    <article className="panel report-preview-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Generated draft</p>
          <h2>{report.title}</h2>
          <p className="panel-intro">{report.summary}</p>
        </div>
        <div className="report-preview-actions">
          <CopyButton text={report.export_markdown || renderFallbackMarkdown(report)} label="report markdown" />
          <button className="secondary-button" type="button" onClick={() => setShowMarkdown((value) => !value)}>
            {showMarkdown ? "Hide markdown" : "Show markdown"}
          </button>
        </div>
      </div>
      <div className="report-safety-note"><strong>Safety:</strong> {report.safety_note}</div>
      <div className="report-section-list">
        {report.sections.map((section) => (
          <section className="report-section-card" key={section.title}>
            <h3>{section.title}</h3>
            <p>{section.content}</p>
            <ul>
              {section.bullets.map((bullet, index) => <li key={`${section.title}-${index}`}>{bullet}</li>)}
            </ul>
          </section>
        ))}
      </div>
      <div className="report-generated-from">
        <strong>Generated from:</strong> {report.generated_from.join(", ")}
      </div>
      {showMarkdown ? <pre className="report-markdown-preview">{report.export_markdown}</pre> : null}
    </article>
  );
}

function renderFallbackMarkdown(report: WorkspaceReport): string {
  const lines = [`# ${report.title}`, "", report.summary, ""];
  for (const section of report.sections) {
    lines.push(`## ${section.title}`, "", section.content, "");
    for (const bullet of section.bullets) lines.push(`- ${bullet}`);
    lines.push("");
  }
  return lines.join("\n");
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}
