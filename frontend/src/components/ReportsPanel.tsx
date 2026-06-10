import { useEffect, useMemo, useState } from "react";

import {
  deleteSavedWorkspaceReport,
  generateWorkspaceReport,
  getWorkspaceReportCatalog,
  listSavedWorkspaceReports,
  pinSavedWorkspaceReport,
  saveWorkspaceReport,
  updateSavedWorkspaceReport,
} from "../api/client";
import type { ReportCatalog, ReportTemplate, SavedWorkspaceReport, WorkspaceReport } from "../api/types";
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
  const [savedReports, setSavedReports] = useState<SavedWorkspaceReport[]>([]);
  const [savedReportsLoading, setSavedReportsLoading] = useState(false);
  const [reportSearch, setReportSearch] = useState("");
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [selectedSavedReport, setSelectedSavedReport] = useState<SavedWorkspaceReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [savingReport, setSavingReport] = useState(false);
  const [savedReportError, setSavedReportError] = useState<string | null>(null);

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

  useEffect(() => {
    void refreshSavedReports();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, reportSearch, pinnedOnly]);

  const selectedTemplate = useMemo(
    () => catalog?.templates.find((template) => template.id === selectedTemplateId) ?? catalog?.templates[0] ?? null,
    [catalog, selectedTemplateId],
  );

  async function refreshSavedReports() {
    setSavedReportsLoading(true);
    setSavedReportError(null);
    try {
      const reports = await listSavedWorkspaceReports(workspaceId, { search: reportSearch, pinnedOnly });
      setSavedReports(reports);
      setSelectedSavedReport((current) => {
        if (!current) return null;
        return reports.find((item) => item.id === current.id) ?? null;
      });
    } catch (error) {
      setSavedReportError(errorMessage(error));
    } finally {
      setSavedReportsLoading(false);
    }
  }

  async function handleGenerate(template: ReportTemplate) {
    setReportLoading(true);
    setReportError(null);
    setSelectedSavedReport(null);
    try {
      const nextReport = await generateWorkspaceReport(workspaceId, template.id);
      setReport(nextReport);
    } catch (error) {
      setReportError(errorMessage(error));
    } finally {
      setReportLoading(false);
    }
  }

  async function handleSaveGeneratedReport() {
    if (!report) return;
    setSavingReport(true);
    setSavedReportError(null);
    try {
      const saved = await saveWorkspaceReport(workspaceId, report.report_type);
      setSelectedSavedReport(saved);
      setReport(null);
      await refreshSavedReports();
    } catch (error) {
      setSavedReportError(errorMessage(error));
    } finally {
      setSavingReport(false);
    }
  }

  async function handlePinReport(savedReport: SavedWorkspaceReport) {
    setSavedReportError(null);
    try {
      const updated = await pinSavedWorkspaceReport(workspaceId, savedReport.id, !savedReport.is_pinned);
      setSelectedSavedReport((current) => (current?.id === updated.id ? updated : current));
      await refreshSavedReports();
    } catch (error) {
      setSavedReportError(errorMessage(error));
    }
  }

  async function handleDeleteReport(savedReport: SavedWorkspaceReport) {
    setSavedReportError(null);
    try {
      await deleteSavedWorkspaceReport(workspaceId, savedReport.id);
      if (selectedSavedReport?.id === savedReport.id) setSelectedSavedReport(null);
      await refreshSavedReports();
    } catch (error) {
      setSavedReportError(errorMessage(error));
    }
  }

  async function handleRenameReport(savedReport: SavedWorkspaceReport) {
    const nextTitle = window.prompt("Report title", savedReport.title);
    if (!nextTitle || nextTitle.trim() === savedReport.title) return;
    setSavedReportError(null);
    try {
      const updated = await updateSavedWorkspaceReport(workspaceId, savedReport.id, { title: nextTitle.trim() });
      setSelectedSavedReport((current) => (current?.id === updated.id ? updated : current));
      await refreshSavedReports();
    } catch (error) {
      setSavedReportError(errorMessage(error));
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
              Generate, save, search, pin, and export read-only report drafts from local workspace evidence.
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

      {report ? (
        <ReportPreview
          report={report}
          onSave={handleSaveGeneratedReport}
          saving={savingReport}
        />
      ) : null}

      <SavedReportsPanel
        reports={savedReports}
        loading={savedReportsLoading}
        error={savedReportError}
        search={reportSearch}
        pinnedOnly={pinnedOnly}
        selectedReport={selectedSavedReport}
        onSearchChange={setReportSearch}
        onPinnedOnlyChange={setPinnedOnly}
        onSelect={(savedReport) => {
          setSelectedSavedReport(savedReport);
          setReport(null);
        }}
        onPin={handlePinReport}
        onDelete={handleDeleteReport}
        onRename={handleRenameReport}
      />
    </section>
  );
}

function ReportPreview({ report, onSave, saving }: { report: WorkspaceReport; onSave: () => void; saving: boolean }) {
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
          <button className="primary-action" type="button" onClick={onSave} disabled={saving}>
            {saving ? "Saving…" : "Save report"}
          </button>
          <CopyButton text={report.export_markdown || renderFallbackMarkdown(report)} label="report markdown" />
          <button className="secondary-button" type="button" onClick={() => setShowMarkdown((value) => !value)}>
            {showMarkdown ? "Hide markdown" : "Show markdown"}
          </button>
        </div>
      </div>
      <div className="report-safety-note"><strong>Safety:</strong> {report.safety_note}</div>
      <ReportSections report={report} />
      {showMarkdown ? <pre className="report-markdown-preview">{report.export_markdown}</pre> : null}
    </article>
  );
}

function SavedReportsPanel({
  reports,
  loading,
  error,
  search,
  pinnedOnly,
  selectedReport,
  onSearchChange,
  onPinnedOnlyChange,
  onSelect,
  onPin,
  onDelete,
  onRename,
}: {
  reports: SavedWorkspaceReport[];
  loading: boolean;
  error: string | null;
  search: string;
  pinnedOnly: boolean;
  selectedReport: SavedWorkspaceReport | null;
  onSearchChange: (value: string) => void;
  onPinnedOnlyChange: (value: boolean) => void;
  onSelect: (report: SavedWorkspaceReport) => void;
  onPin: (report: SavedWorkspaceReport) => void;
  onDelete: (report: SavedWorkspaceReport) => void;
  onRename: (report: SavedWorkspaceReport) => void;
}) {
  return (
    <div className="reports-layout saved-reports-layout">
      <div className="panel saved-reports-panel">
        <div className="panel-heading compact-heading">
          <div>
            <p className="eyebrow">Report history</p>
            <h3>Saved reports</h3>
          </div>
          <span className="panel-count">{reports.length}</span>
        </div>
        <div className="conversation-filter-row">
          <input
            className="text-input"
            placeholder="Search reports"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
          <label className="checkbox-row compact-checkbox">
            <input
              type="checkbox"
              checked={pinnedOnly}
              onChange={(event) => onPinnedOnlyChange(event.target.checked)}
            />
            Pinned only
          </label>
        </div>
        {error ? <ErrorState title="Saved reports unavailable" message={error} compact /> : null}
        {loading ? <p className="form-help">Loading saved reports…</p> : null}
        {!loading && reports.length === 0 ? (
          <EmptyState title="No saved reports yet" message="Generate a report draft, then save it to keep it in this workspace." compact />
        ) : null}
        <div className="report-template-list">
          {reports.map((savedReport) => (
            <button
              key={savedReport.id}
              type="button"
              className={`report-template-card${selectedReport?.id === savedReport.id ? " is-selected" : ""}`}
              onClick={() => onSelect(savedReport)}
            >
              <strong>{savedReport.is_pinned ? "★ " : ""}{savedReport.title}</strong>
              <span>{savedReport.summary}</span>
              <small>{savedReport.report_type} · {formatDate(savedReport.updated_at)}</small>
            </button>
          ))}
        </div>
      </div>

      <div className="panel report-generator-panel">
        {selectedReport ? (
          <SavedReportDetails
            report={selectedReport}
            onPin={onPin}
            onDelete={onDelete}
            onRename={onRename}
          />
        ) : (
          <EmptyState title="Select a saved report" message="Open a report to copy, export, pin, rename, or delete it." compact />
        )}
      </div>
    </div>
  );
}

function SavedReportDetails({
  report,
  onPin,
  onDelete,
  onRename,
}: {
  report: SavedWorkspaceReport;
  onPin: (report: SavedWorkspaceReport) => void;
  onDelete: (report: SavedWorkspaceReport) => void;
  onRename: (report: SavedWorkspaceReport) => void;
}) {
  const [showMarkdown, setShowMarkdown] = useState(false);
  const [showText, setShowText] = useState(false);
  return (
    <article className="saved-report-details">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Saved report</p>
          <h3>{report.title}</h3>
          <p className="panel-intro">{report.summary}</p>
        </div>
        <StatusBadge label={report.is_pinned ? "Pinned" : "Saved"} />
      </div>
      <dl className="report-template-details">
        <div><dt>Type</dt><dd>{report.report_type}</dd></div>
        <div><dt>Updated</dt><dd>{formatDate(report.updated_at)}</dd></div>
        <div><dt>Sources</dt><dd>{report.generated_from.join(", ") || "—"}</dd></div>
      </dl>
      <div className="report-preview-actions">
        <button className="secondary-button" type="button" onClick={() => onPin(report)}>
          {report.is_pinned ? "Unpin" : "Pin"}
        </button>
        <button className="secondary-button" type="button" onClick={() => onRename(report)}>Rename</button>
        <CopyButton text={report.export_markdown} label="markdown" />
        <CopyButton text={report.export_text} label="text" />
        <CopyButton text={JSON.stringify(report.report_json, null, 2)} label="json" />
        <button className="secondary-button" type="button" onClick={() => setShowMarkdown((value) => !value)}>
          {showMarkdown ? "Hide md" : "Show md"}
        </button>
        <button className="secondary-button" type="button" onClick={() => setShowText((value) => !value)}>
          {showText ? "Hide text" : "Show text"}
        </button>
        <button className="danger-button" type="button" onClick={() => onDelete(report)}>Delete</button>
      </div>
      {showMarkdown ? <pre className="report-markdown-preview">{report.export_markdown}</pre> : null}
      {showText ? <pre className="report-markdown-preview">{report.export_text}</pre> : null}
    </article>
  );
}

function ReportSections({ report }: { report: WorkspaceReport }) {
  return (
    <>
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
    </>
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

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}
