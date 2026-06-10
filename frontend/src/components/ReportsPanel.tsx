import { useEffect, useMemo, useState } from "react";

import {
  buildCustomWorkspaceReport,
  deleteSavedWorkspaceReport,
  generateWorkspaceReport,
  getWorkspaceReportCatalog,
  listWorkspaceAnswerNotes,
  listWorkspaceConversations,
  listSavedWorkspaceReports,
  pinSavedWorkspaceReport,
  saveCustomWorkspaceReport,
  saveEditedWorkspaceReport,
  updateSavedWorkspaceReport,
} from "../api/client";
import type { ConversationAnswerNote, ReportCatalog, ReportQualitySummary, ReportSection, ReportTemplate, SavedWorkspaceReport, WorkspaceConversation, WorkspaceReport } from "../api/types";
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
  const [builderNotes, setBuilderNotes] = useState<ConversationAnswerNote[]>([]);
  const [builderConversations, setBuilderConversations] = useState<WorkspaceConversation[]>([]);
  const [selectedNoteIds, setSelectedNoteIds] = useState<string[]>([]);
  const [selectedConversationIds, setSelectedConversationIds] = useState<string[]>([]);
  const [customReportTitle, setCustomReportTitle] = useState("Custom workspace report");
  const [customReportContext, setCustomReportContext] = useState("");
  const [customReportLoading, setCustomReportLoading] = useState(false);

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


  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listWorkspaceAnswerNotes(workspaceId),
      listWorkspaceConversations(workspaceId, { includeArchived: false }),
    ])
      .then(([notes, conversations]) => {
        if (cancelled) return;
        setBuilderNotes(notes);
        setBuilderConversations(conversations);
      })
      .catch(() => {
        if (cancelled) return;
        setBuilderNotes([]);
        setBuilderConversations([]);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

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

  async function handleSaveGeneratedReport(editedReport: WorkspaceReport, markdown: string) {
    setSavingReport(true);
    setSavedReportError(null);
    try {
      const saved = await saveEditedWorkspaceReport(workspaceId, {
        title: editedReport.title,
        summary: editedReport.summary,
        report_type: editedReport.report_type,
        sections: editedReport.sections,
        generated_from: editedReport.generated_from,
        export_markdown: markdown,
        safety_note: editedReport.safety_note,
      });
      setSelectedSavedReport(saved);
      setReport(null);
      await refreshSavedReports();
    } catch (error) {
      setSavedReportError(errorMessage(error));
    } finally {
      setSavingReport(false);
    }
  }


  function customReportRequest() {
    return {
      title: customReportTitle,
      summary: "Custom report assembled from selected workspace notes and conversations.",
      report_type: "custom_report",
      note_ids: selectedNoteIds,
      conversation_ids: selectedConversationIds,
      extra_context: customReportContext,
    };
  }

  async function handleBuildCustomReport() {
    setCustomReportLoading(true);
    setReportError(null);
    setSelectedSavedReport(null);
    try {
      const nextReport = await buildCustomWorkspaceReport(workspaceId, customReportRequest());
      setReport(nextReport);
    } catch (error) {
      setReportError(errorMessage(error));
    } finally {
      setCustomReportLoading(false);
    }
  }

  async function handleSaveCustomReport() {
    setCustomReportLoading(true);
    setSavedReportError(null);
    try {
      const saved = await saveCustomWorkspaceReport(workspaceId, customReportRequest());
      setSelectedSavedReport(saved);
      setReport(null);
      await refreshSavedReports();
    } catch (error) {
      setSavedReportError(errorMessage(error));
    } finally {
      setCustomReportLoading(false);
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

  async function handleUpdateReportContent(savedReport: SavedWorkspaceReport, request: { title: string; summary: string; export_markdown: string }) {
    setSavedReportError(null);
    try {
      const updated = await updateSavedWorkspaceReport(workspaceId, savedReport.id, {
        title: request.title,
        summary: request.summary,
        export_markdown: request.export_markdown,
        report_json: {
          ...savedReport.report_json,
          title: request.title,
          summary: request.summary,
          export_markdown: request.export_markdown,
          edited_in_workspace: true,
        },
      });
      setSelectedSavedReport(updated);
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

      <CustomReportBuilder
        notes={builderNotes}
        conversations={builderConversations}
        selectedNoteIds={selectedNoteIds}
        selectedConversationIds={selectedConversationIds}
        title={customReportTitle}
        extraContext={customReportContext}
        loading={customReportLoading}
        onTitleChange={setCustomReportTitle}
        onExtraContextChange={setCustomReportContext}
        onSelectedNoteIdsChange={setSelectedNoteIds}
        onSelectedConversationIdsChange={setSelectedConversationIds}
        onPreview={handleBuildCustomReport}
        onSave={handleSaveCustomReport}
      />

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
        onUpdate={handleUpdateReportContent}
      />
    </section>
  );
}

function CustomReportBuilder({
  notes,
  conversations,
  selectedNoteIds,
  selectedConversationIds,
  title,
  extraContext,
  loading,
  onTitleChange,
  onExtraContextChange,
  onSelectedNoteIdsChange,
  onSelectedConversationIdsChange,
  onPreview,
  onSave,
}: {
  notes: ConversationAnswerNote[];
  conversations: WorkspaceConversation[];
  selectedNoteIds: string[];
  selectedConversationIds: string[];
  title: string;
  extraContext: string;
  loading: boolean;
  onTitleChange: (value: string) => void;
  onExtraContextChange: (value: string) => void;
  onSelectedNoteIdsChange: (value: string[]) => void;
  onSelectedConversationIdsChange: (value: string[]) => void;
  onPreview: () => void;
  onSave: () => void;
}) {
  const selectedCount = selectedNoteIds.length + selectedConversationIds.length;
  function toggleNote(noteId: string) {
    onSelectedNoteIdsChange(
      selectedNoteIds.includes(noteId)
        ? selectedNoteIds.filter((id) => id !== noteId)
        : [...selectedNoteIds, noteId],
    );
  }
  function toggleConversation(conversationId: string) {
    onSelectedConversationIdsChange(
      selectedConversationIds.includes(conversationId)
        ? selectedConversationIds.filter((id) => id !== conversationId)
        : [...selectedConversationIds, conversationId],
    );
  }
  return (
    <section className="panel custom-report-builder">
      <div className="panel-heading compact-heading">
        <div>
          <p className="eyebrow">Custom builder</p>
          <h3>Build from selected notes and conversations</h3>
          <p className="panel-intro">
            Select reusable workspace evidence, add drafting notes, then preview or save a custom report. Nothing runs automatically.
          </p>
        </div>
        <StatusBadge label={`${selectedCount} selected`} tone={selectedCount > 0 ? "neutral" : "warning"} />
      </div>
      <div className="custom-report-grid">
        <div className="custom-report-column">
          <label className="field-label" htmlFor="custom-report-title">Report title</label>
          <input
            id="custom-report-title"
            className="text-input"
            value={title}
            onChange={(event) => onTitleChange(event.target.value)}
          />
          <label className="field-label" htmlFor="custom-report-context">Drafting notes</label>
          <textarea
            id="custom-report-context"
            className="textarea-input custom-report-textarea"
            value={extraContext}
            onChange={(event) => onExtraContextChange(event.target.value)}
            placeholder="Optional: target audience, sections to emphasize, ticket/doc purpose…"
          />
        </div>
        <div className="custom-report-column">
          <strong>Saved notes</strong>
          <div className="custom-report-picker">
            {notes.slice(0, 8).map((note) => (
              <label className="checkbox-row compact-checkbox" key={note.id}>
                <input type="checkbox" checked={selectedNoteIds.includes(note.id)} onChange={() => toggleNote(note.id)} />
                <span>{note.is_pinned ? "★ " : ""}{note.title}</span>
              </label>
            ))}
            {notes.length === 0 ? <span className="form-help">No saved notes yet.</span> : null}
          </div>
        </div>
        <div className="custom-report-column">
          <strong>Conversations</strong>
          <div className="custom-report-picker">
            {conversations.slice(0, 8).map((conversation) => (
              <label className="checkbox-row compact-checkbox" key={conversation.id}>
                <input
                  type="checkbox"
                  checked={selectedConversationIds.includes(conversation.id)}
                  onChange={() => toggleConversation(conversation.id)}
                />
                <span>{conversation.is_pinned ? "★ " : ""}{conversation.title}</span>
              </label>
            ))}
            {conversations.length === 0 ? <span className="form-help">No saved conversations yet.</span> : null}
          </div>
        </div>
      </div>
      <div className="report-action-row">
        <button className="secondary-button" type="button" disabled={loading} onClick={onPreview}>
          {loading ? "Building…" : "Preview custom report"}
        </button>
        <button className="primary-action" type="button" disabled={loading} onClick={onSave}>
          {loading ? "Saving…" : "Save custom report"}
        </button>
        <span className="form-help">Read-only builder: no scan, index, rebuild, command execution, or upload.</span>
      </div>
    </section>
  );
}

function ReportPreview({
  report,
  onSave,
  saving,
}: {
  report: WorkspaceReport;
  onSave: (report: WorkspaceReport, markdown: string) => void;
  saving: boolean;
}) {
  const [showMarkdown, setShowMarkdown] = useState(false);
  const [selectedSections, setSelectedSections] = useState<string[]>(report.sections.map((section) => section.title));
  const [sectionOrder, setSectionOrder] = useState<string[]>(report.sections.map((section) => section.title));
  const [draftTitle, setDraftTitle] = useState(report.title);
  const [draftSummary, setDraftSummary] = useState(report.summary);
  const [draftMarkdown, setDraftMarkdown] = useState(report.export_markdown || renderFallbackMarkdown(report));

  const visibleSections = sectionOrder
    .map((title) => report.sections.find((section) => section.title === title))
    .filter((section): section is ReportSection => Boolean(section))
    .filter((section) => selectedSections.includes(section.title));
  const documentationMarkdown = renderDocumentationMarkdown({
    ...report,
    title: draftTitle,
    summary: draftSummary,
    sections: visibleSections,
    export_markdown: draftMarkdown,
  });

  function toggleSection(title: string) {
    setSelectedSections((current) => (
      current.includes(title)
        ? current.filter((item) => item !== title)
        : [...current, title]
    ));
  }

  function moveSection(title: string, direction: -1 | 1) {
    setSectionOrder((current) => {
      const index = current.indexOf(title);
      const nextIndex = index + direction;
      if (index < 0 || nextIndex < 0 || nextIndex >= current.length) return current;
      const next = [...current];
      [next[index], next[nextIndex]] = [next[nextIndex], next[index]];
      return next;
    });
  }

  function saveEditedDraft() {
    onSave(
      {
        ...report,
        title: draftTitle,
        summary: draftSummary,
        sections: visibleSections,
        export_markdown: draftMarkdown,
      },
      draftMarkdown,
    );
  }

  return (
    <article className="panel report-preview-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Editable generated draft</p>
          <h2>{draftTitle}</h2>
          <p className="panel-intro">Review, trim, reorder, and edit the markdown before saving a documentation-ready report.</p>
        </div>
        <div className="report-preview-actions">
          <button className="primary-action" type="button" onClick={saveEditedDraft} disabled={saving || selectedSections.length === 0}>
            {saving ? "Saving…" : "Save edited report"}
          </button>
          <CopyButton text={draftMarkdown} label="editable markdown" />
          <CopyButton text={documentationMarkdown} label="documentation-ready markdown" />
          <button className="secondary-button" type="button" onClick={() => setDraftMarkdown(documentationMarkdown)}>
            Use doc-ready markdown
          </button>
          <button className="secondary-button" type="button" onClick={() => setShowMarkdown((value) => !value)}>
            {showMarkdown ? "Hide editor" : "Show editor"}
          </button>
        </div>
      </div>
      <div className="report-safety-note"><strong>Safety:</strong> {report.safety_note}</div>
      <ReportQualityCard quality={report.quality} compact={false} />
      <div className="report-editor-grid">
        <label className="field-label">Report title
          <input className="text-input" value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} />
        </label>
        <label className="field-label">Summary
          <textarea className="report-editor-textarea compact" value={draftSummary} onChange={(event) => setDraftSummary(event.target.value)} />
        </label>
      </div>
      <div className="report-section-editor">
        <div className="panel-heading compact-heading">
          <div>
            <p className="eyebrow">Sections</p>
            <h3>Choose and order sections</h3>
          </div>
          <StatusBadge label={`${selectedSections.length}/${report.sections.length} included`} />
        </div>
        <div className="report-section-toggle-list">
          {sectionOrder.map((title, index) => {
            const section = report.sections.find((item) => item.title === title);
            if (!section) return null;
            return (
              <div className="report-section-toggle" key={section.title}>
                <label className="checkbox-row compact-checkbox">
                  <input type="checkbox" checked={selectedSections.includes(section.title)} onChange={() => toggleSection(section.title)} />
                  <span>{section.title}</span>
                </label>
                <div className="report-section-toggle-actions">
                  <button className="secondary-button tiny-button" type="button" disabled={index === 0} onClick={() => moveSection(section.title, -1)}>Up</button>
                  <button className="secondary-button tiny-button" type="button" disabled={index === sectionOrder.length - 1} onClick={() => moveSection(section.title, 1)}>Down</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <ReportSections report={{ ...report, title: draftTitle, summary: draftSummary, sections: visibleSections }} />
      {showMarkdown ? (
        <div className="report-markdown-editor-block">
          <label className="field-label">Editable markdown
            <textarea className="report-markdown-editor" value={draftMarkdown} onChange={(event) => setDraftMarkdown(event.target.value)} />
          </label>
          <div className="report-export-grid">
            <div>
              <strong>Documentation-ready Markdown</strong>
              <pre className="report-markdown-preview compact-preview">{documentationMarkdown}</pre>
            </div>
            <div>
              <strong>Plain text export</strong>
              <pre className="report-markdown-preview compact-preview">{markdownToPlainText(draftMarkdown)}</pre>
            </div>
          </div>
        </div>
      ) : null}
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
  onUpdate,
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
  onUpdate: (report: SavedWorkspaceReport, request: { title: string; summary: string; export_markdown: string }) => void;
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
              <small>{savedReport.report_type} · Quality {savedReport.quality.score}% · {savedReport.quality.source_coverage_label} sources · {formatDate(savedReport.updated_at)}</small>
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
            onUpdate={onUpdate}
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
  onUpdate,
}: {
  report: SavedWorkspaceReport;
  onPin: (report: SavedWorkspaceReport) => void;
  onDelete: (report: SavedWorkspaceReport) => void;
  onRename: (report: SavedWorkspaceReport) => void;
  onUpdate: (report: SavedWorkspaceReport, request: { title: string; summary: string; export_markdown: string }) => void;
}) {
  const [showMarkdown, setShowMarkdown] = useState(false);
  const [showText, setShowText] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(report.title);
  const [draftSummary, setDraftSummary] = useState(report.summary);
  const [draftMarkdown, setDraftMarkdown] = useState(report.export_markdown);

  useEffect(() => {
    setDraftTitle(report.title);
    setDraftSummary(report.summary);
    setDraftMarkdown(report.export_markdown);
    setEditing(false);
  }, [report.id, report.title, report.summary, report.export_markdown]);

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
      <ReportQualityCard quality={report.quality} compact={false} />
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
        <button className="secondary-button" type="button" onClick={() => setEditing((value) => !value)}>
          {editing ? "Close editor" : "Edit saved report"}
        </button>
        <CopyButton text={report.export_markdown} label="markdown" />
        <CopyButton text={report.export_text} label="text" />
        <CopyButton text={JSON.stringify(report.report_json, null, 2)} label="json" />
        <CopyButton text={renderDocumentationReadyMarkdown(report)} label="doc-ready md" />
        <button className="secondary-button" type="button" onClick={() => setShowMarkdown((value) => !value)}>
          {showMarkdown ? "Hide md" : "Show md"}
        </button>
        <button className="secondary-button" type="button" onClick={() => setShowText((value) => !value)}>
          {showText ? "Hide text" : "Show text"}
        </button>
        <button className="danger-button" type="button" onClick={() => onDelete(report)}>Delete</button>
      </div>
      {editing ? (
        <div className="saved-report-editor">
          <label className="field-label">Title
            <input className="text-input" value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} />
          </label>
          <label className="field-label">Summary
            <textarea className="report-editor-textarea compact" value={draftSummary} onChange={(event) => setDraftSummary(event.target.value)} />
          </label>
          <label className="field-label">Markdown
            <textarea className="report-markdown-editor" value={draftMarkdown} onChange={(event) => setDraftMarkdown(event.target.value)} />
          </label>
          <div className="report-preview-actions">
            <button className="primary-action" type="button" onClick={() => onUpdate(report, { title: draftTitle, summary: draftSummary, export_markdown: draftMarkdown })}>
              Save edits
            </button>
            <button className="secondary-button" type="button" onClick={() => setDraftMarkdown(renderDocumentationReadyMarkdown(report))}>
              Reset to doc-ready format
            </button>
          </div>
        </div>
      ) : null}
      {showMarkdown ? <pre className="report-markdown-preview">{report.export_markdown}</pre> : null}
      {showText ? <pre className="report-markdown-preview">{report.export_text}</pre> : null}
    </article>
  );
}


function ReportQualityCard({ quality, compact }: { quality: ReportQualitySummary; compact?: boolean }) {
  const failedChecks = quality.checks.filter((check) => check.status !== "pass");
  return (
    <section className={`report-quality-card${compact ? " compact" : ""}`}>
      <div className="report-quality-header">
        <div>
          <p className="eyebrow">Quality check</p>
          <strong>{quality.score}% · {quality.status.replace("_", " ")}</strong>
        </div>
        <StatusBadge label={`${quality.source_coverage_count} evidence refs`} tone={quality.source_coverage_count > 0 ? "neutral" : "warning"} />
      </div>
      <div className="report-quality-grid">
        {quality.checks.map((check) => (
          <div className={`report-quality-check is-${check.status}`} key={check.id}>
            <strong>{check.status === "pass" ? "✓" : "!"} {check.label}</strong>
            {!compact || check.status !== "pass" ? <span>{check.detail}</span> : null}
          </div>
        ))}
      </div>
      {failedChecks.length > 0 ? (
        <p className="form-help">Review recommended: {failedChecks.map((check) => check.label).join(", ")}.</p>
      ) : (
        <p className="form-help">Ready for human review. Quality checks do not replace source verification.</p>
      )}
    </section>
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


function renderDocumentationMarkdown(report: WorkspaceReport): string {
  const lines = [
    `# ${report.title}`,
    "",
    report.summary,
    "",
    `> Safety: ${report.safety_note}`,
    "",
  ];
  for (const section of report.sections) {
    lines.push(`## ${section.title}`, "", section.content, "");
    for (const bullet of section.bullets) lines.push(`- ${bullet}`);
    lines.push("");
  }
  lines.push("## Generated from", "");
  for (const source of report.generated_from) lines.push(`- ${source}`);
  lines.push("", "---", "", "Generated locally by AI Private Workspace. Review before sharing.", "");
  return lines.join("\n");
}

function renderDocumentationReadyMarkdown(report: SavedWorkspaceReport): string {
  const sections = Array.isArray(report.report_json.sections) ? report.report_json.sections : [];
  const lines = [
    `# ${report.title}`,
    "",
    report.summary,
    "",
    "> Safety: Saved report generated from local workspace evidence. Review before sharing.",
    "",
  ];
  for (const rawSection of sections) {
    if (!rawSection || typeof rawSection !== "object") continue;
    const section = rawSection as { title?: unknown; content?: unknown; bullets?: unknown };
    const title = typeof section.title === "string" ? section.title : "Section";
    const content = typeof section.content === "string" ? section.content : "";
    const bullets = Array.isArray(section.bullets) ? section.bullets : [];
    lines.push(`## ${title}`, "", content, "");
    for (const bullet of bullets) lines.push(`- ${String(bullet)}`);
    lines.push("");
  }
  lines.push("## Generated from", "");
  for (const source of report.generated_from) lines.push(`- ${source}`);
  lines.push("", "---", "", "Generated locally by AI Private Workspace. Review before sharing.", "");
  return lines.join("\n");
}

function markdownToPlainText(markdown: string): string {
  return markdown
    .split("\n")
    .map((line) => line.replace(/^#{1,6}\s*/, "").replace(/^>\s*/, "").replace(/`/g, "").replace(/\*\*/g, ""))
    .join("\n")
    .trim();
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}
