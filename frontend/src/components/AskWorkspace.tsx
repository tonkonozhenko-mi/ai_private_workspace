import { FormEvent, useEffect, useState } from "react";

import { askSelectedWorkspace } from "../api/client";
import { CopyButton } from "./CopyButton";
import type {
  RagQualityWarning,
  RagSource,
  WorkspaceQuestionAnswer,
} from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";

interface AskWorkspaceProps {
  workspaceId: string;
  onAsked?: () => void | Promise<void>;
}

interface AskHistoryItem {
  id: string;
  question: string;
  answer: string;
  llmLabel: string;
  sourcesCount: number;
  warningsCount: number;
  createdAt: string;
  response: WorkspaceQuestionAnswer;
}

const PROJECT_QUESTION_KEYWORDS = new Set([
  "terraform",
  "terragrunt",
  "docker",
  "kubernetes",
  "helm",
  "gitlab",
  "github",
  "pipeline",
  "ci",
  "cd",
  "backend",
  "frontend",
  "code",
  "file",
  "project",
  "config",
  "configuration",
  "deployment",
  "dependency",
  "module",
  "state",
  "workspace",
  "error",
  "issue",
  "test",
]);

const EXAMPLE_QUESTIONS = [
  "How is Terraform backend configured?",
  "Which CI/CD systems are detected?",
  "What should I review first in this project?",
  "Are there any model/runtime setup issues?",
  "What files are related to Kubernetes or Helm?",
];

export function AskWorkspace({ workspaceId, onAsked }: AskWorkspaceProps) {
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState(5);
  const [history, setHistory] = useState<AskHistoryItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const selectedHistoryItem =
    history.find((item) => item.id === selectedHistoryId) ?? history[0] ?? null;
  const showGeneralQuestionHint =
    question.trim().length > 0 && !isLikelyProjectQuestion(question);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      setError("Enter a workspace question before asking.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await askSelectedWorkspace(
        workspaceId,
        trimmedQuestion,
        limit,
      );
      const historyItem = createHistoryItem(result);
      setHistory((current) => [historyItem, ...current].slice(0, 10));
      setSelectedHistoryId(historyItem.id);
      await onAsked?.();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not ask the selected workspace LLM.",
      );
    } finally {
      setLoading(false);
    }
  }

  const missingSelectedLLM =
    error?.toLowerCase().includes("selected llm") ||
    error?.toLowerCase().includes("select an llm");

  return (
    <div className="ask-workspace">
      <div className="ask-sidebar">
        <section className="panel ask-composer ask-composer-native">
          <div className="panel-heading ask-composer-heading">
            <div>
              <p className="eyebrow">Selected workspace LLM</p>
              <h2>Ask this workspace</h2>
              <p className="ask-composer-subtitle">
                Ask about code, infrastructure, CI/CD, or setup. The answer uses
                indexed project context and keeps sources visible.
              </p>
            </div>
            <StatusBadge label="Manual Submit" />
          </div>

          <p className="ask-safety-note">
            Local workspace context only. Nothing is sent until you press Ask,
            and this never executes commands or changes runtime settings.
          </p>

          <form onSubmit={(event) => void submitQuestion(event)}>
            <label htmlFor="workspace-question">Question</label>
            <textarea
              id="workspace-question"
              placeholder="How is Terraform backend configured?"
              rows={5}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
            />

            {showGeneralQuestionHint ? (
              <p className="ask-question-hint">
                This looks like a general chat question. Workspace Ask works
                best with project, code, infrastructure, CI/CD, or configuration
                questions.
              </p>
            ) : null}

            <div className="ask-examples">
              <span>Example questions</span>
              <div>
                {EXAMPLE_QUESTIONS.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => {
                      setQuestion(example);
                      setError(null);
                    }}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>

            <div className="ask-controls">
              <label>
                Context chunks
                <select
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                >
                  <option value={3}>3</option>
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                </select>
              </label>
              <button
                className="primary-button"
                type="submit"
                disabled={loading || question.trim().length === 0}
              >
                {loading ? "Asking..." : "Ask"}
              </button>
            </div>
          </form>

          {error ? (
            <div className="ask-error" role="alert">
              <strong>Could not ask workspace</strong>
              <span>{error}</span>
              {missingSelectedLLM ? (
                <span>Select an LLM in the Models tab, then try again.</span>
              ) : null}
            </div>
          ) : null}
        </section>

        <SessionHistory
          history={history}
          selectedHistoryId={selectedHistoryItem?.id ?? null}
          onSelect={setSelectedHistoryId}
          onClear={() => {
            setHistory([]);
            setSelectedHistoryId(null);
          }}
        />
      </div>

      {selectedHistoryItem ? (
        <AnswerResult answer={selectedHistoryItem.response} />
      ) : (
        <AskEmptyState />
      )}
    </div>
  );
}

function SessionHistory({
  history,
  selectedHistoryId,
  onSelect,
  onClear,
}: {
  history: AskHistoryItem[];
  selectedHistoryId: string | null;
  onSelect: (id: string) => void;
  onClear: () => void;
}) {
  return (
    <section className="panel ask-history-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Current browser tab</p>
          <h2>Recent questions</h2>
        </div>
        <span className="panel-count">{history.length}</span>
      </div>

      <p className="ask-history-note">
        Local to this browser tab. Pick a previous question to review its answer
        and sources.
      </p>

      {history.length > 0 ? (
        <>
          <div className="ask-history-list">
            {history.map((item) => (
              <button
                aria-pressed={selectedHistoryId === item.id}
                className={`ask-history-item${
                  selectedHistoryId === item.id ? " is-selected" : ""
                }`}
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
              >
                <strong>{item.question}</strong>
                <p>{item.answer || "Empty answer"}</p>
                <div>
                  <span>{item.llmLabel}</span>
                  <span>{item.sourcesCount} sources</span>
                  <span>{item.warningsCount} warnings</span>
                  <time dateTime={item.createdAt}>
                    {formatTime(item.createdAt)}
                  </time>
                </div>
              </button>
            ))}
          </div>
          <button
            className="session-clear-button"
            type="button"
            onClick={onClear}
          >
            Clear session history
          </button>
        </>
      ) : (
        <EmptyState title="No questions asked in this session yet" compact />
      )}
    </section>
  );
}

function AnswerResult({ answer }: { answer: WorkspaceQuestionAnswer }) {
  const warnings = answer.quality_warnings ?? [];
  const reindexReason = getAskReindexReason(answer);
  const isMissingSourcePaths = warnings.some(
    (warning) => warning.code === "answer_missing_source_paths",
  );

  return (
    <section className="ask-results" aria-live="polite">
      <article className="panel answer-panel">
        <div className="panel-heading answer-heading">
          <div>
            <p className="eyebrow">Workspace answer</p>
            <h2>Answer from selected model</h2>
          </div>
          <span className="answer-model">
            {answer.llm_provider}/{answer.llm_model ?? "default"}
          </span>
        </div>
        <div className="answer-question-card">
          <span>You asked</span>
          <p>{answer.question}</p>
        </div>
        <div className="answer-content answer-bubble">
          {answer.answer ? (
            <MarkdownAnswer content={answer.answer} />
          ) : (
            "The selected LLM returned an empty answer."
          )}
        </div>
        <div className="answer-stats">
          <span>
            <strong>{answer.used_context_chunks}</strong> context chunks used
          </span>
          <span>
            <strong>{answer.sources.length}</strong> sources returned
          </span>
        </div>
      </article>

      {answer.diagnostic_message ? (
        <article className="ask-diagnostic">
          <span>{formatLabel(answer.diagnostic_code ?? "workspace status")}</span>
          <p>{answer.diagnostic_message}</p>
        </article>
      ) : null}

      {reindexReason ? (
        <ReindexGuidance
          workspaceId={answer.workspace_id}
          reason={reindexReason}
        />
      ) : null}

      {warnings.length > 0 ? <QualityWarnings warnings={warnings} /> : null}

      {isMissingSourcePaths ? (
        <p className="ask-source-path-note">
          The model answered without mentioning source paths. Check retrieved
          sources below.
        </p>
      ) : null}

      <Sources
        workspaceId={answer.workspace_id}
        sources={answer.sources}
        suppressReindexGuidance={reindexReason !== null}
      />
    </section>
  );
}

function QualityWarnings({ warnings }: { warnings: RagQualityWarning[] }) {
  return (
    <section className="panel quality-warnings">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Answer verification</p>
          <h2>Verification notes</h2>
        </div>
        <span className="panel-count">{warnings.length}</span>
      </div>
      <div className="quality-warning-list">
        {warnings.map((warning, index) => (
          <article key={`${warning.code}-${index}`}>
            <StatusBadge label={warning.severity} />
            <div>
              <strong>{formatLabel(warning.code)}</strong>
              <p>{warning.message}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function Sources({
  workspaceId,
  sources,
  suppressReindexGuidance = false,
}: {
  workspaceId: string;
  sources: RagSource[];
  suppressReindexGuidance?: boolean;
}) {
  const [showAllSources, setShowAllSources] = useState(false);
  const [expandedSourceIds, setExpandedSourceIds] = useState<Set<string>>(
    () => new Set(sources.slice(0, 1).map((source) => source.chunk_id)),
  );
  const topSourceScoreIsLow = sources.length > 0 && sources[0].score < 0.25;
  const visibleSources = showAllSources ? sources : sources.slice(0, 2);
  const hiddenSourcesCount = Math.max(sources.length - visibleSources.length, 0);

  useEffect(() => {
    setShowAllSources(false);
    setExpandedSourceIds(
      new Set(sources.slice(0, 1).map((source) => source.chunk_id)),
    );
  }, [sources]);

  function toggleSourcePreview(sourceId: string) {
    setExpandedSourceIds((current) => {
      const next = new Set(current);
      if (next.has(sourceId)) {
        next.delete(sourceId);
      } else {
        next.add(sourceId);
      }
      return next;
    });
  }

  return (
    <section className="panel source-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Retrieved context</p>
          <h2>Verify with sources</h2>
        </div>
        <span className="source-count-summary">
          {sources.length} retrieved{" "}
          {sources.length === 1 ? "source" : "sources"}
        </span>
      </div>
      {sources.length > 0 ? (
        <>
          <p className="source-panel-subtitle">
            Showing the strongest sources first. Expand previews only when you
            need to verify a claim.
          </p>
          {topSourceScoreIsLow ? (
            <p className="source-quality-hint">
              Top source score is low; answer may be weakly grounded.
            </p>
          ) : null}
          <div className="source-list">
            {visibleSources.map((source) => {
              const detectedType = source.metadata?.detected_type;
              const extension = source.metadata?.extension;
              const isExpanded = expandedSourceIds.has(source.chunk_id);
              const globalIndex = sources.findIndex(
                (candidate) => candidate.chunk_id === source.chunk_id,
              );

              return (
                <article
                  className={globalIndex === 0 ? "is-top-source" : undefined}
                  key={source.chunk_id}
                >
                  <div className="source-card-heading">
                    <div>
                      {globalIndex === 0 ? (
                        <span className="top-source-badge">Top source</span>
                      ) : null}
                      <strong title={source.source_path}>
                        {source.source_path}
                      </strong>
                    </div>
                    <span className="source-score">
                      {formatSourceScore(source.score)} match
                    </span>
                  </div>
                  {detectedType || extension ? (
                    <div className="source-metadata">
                      {detectedType ? (
                        <span>{formatLabel(detectedType)}</span>
                      ) : null}
                      {extension ? <span>{extension}</span> : null}
                    </div>
                  ) : null}
                  <button
                    className="source-preview-toggle"
                    type="button"
                    aria-expanded={isExpanded}
                    onClick={() => toggleSourcePreview(source.chunk_id)}
                  >
                    {isExpanded ? "Hide preview" : "Show preview"}
                  </button>
                  {isExpanded ? (
                    <pre className="source-preview">{source.preview}</pre>
                  ) : null}
                </article>
              );
            })}
          </div>
          {sources.length > 2 ? (
            <div className="source-disclosure-footer">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setShowAllSources((current) => !current)}
              >
                {showAllSources
                  ? "Show top sources only"
                  : `Show all sources (${hiddenSourcesCount} more)`}
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <>
          <EmptyState
            title="No sources returned"
            message="Try reindexing or asking a more project-specific question."
            compact
          />
          {!suppressReindexGuidance ? (
            <ReindexGuidance
              workspaceId={workspaceId}
              reason="No sources were returned. If this workspace should have indexed context, rerun indexing manually."
            />
          ) : null}
        </>
      )}
    </section>
  );
}

function ReindexGuidance({
  workspaceId,
  reason,
}: {
  workspaceId: string;
  reason: string;
}) {
  const scanCommand = `curl -X POST http://127.0.0.1:8000/workspaces/${workspaceId}/scan`;
  const indexCommand = `curl -X POST http://127.0.0.1:8000/workspaces/${workspaceId}/index`;

  return (
    <article className="reindex-guidance">
      <div>
        <StatusBadge label="instructions only" />
        <strong>Scan and reindex guidance</strong>
      </div>
      <p>{reason}</p>
      <p>
        If the project has not been scanned yet, run scan first. Then rebuild
        the workspace index.
      </p>
      <CommandGuidanceRow label="Step 1 · scan project" command={scanCommand} />
      <CommandGuidanceRow label="Step 2 · build index" command={indexCommand} />
      <small>
        The frontend does not run scan or indexing automatically. Copy and run
        these commands yourself when you intentionally want to rebuild the
        workspace context.
      </small>
    </article>
  );
}

function CommandGuidanceRow({
  label,
  command,
}: {
  label: string;
  command: string;
}) {
  return (
    <div className="reindex-command-step">
      <span>{label}</span>
      <div className="reindex-command-row">
        <code title={command}>{command}</code>
        <CopyButton text={command} />
      </div>
    </div>
  );
}

function getAskReindexReason(answer: WorkspaceQuestionAnswer): string | null {
  const diagnosticCode = answer.diagnostic_code?.toLowerCase() ?? "";
  const diagnosticMessage = answer.diagnostic_message?.toLowerCase() ?? "";

  if (diagnosticCode.includes("workspace_not_indexed")) {
    return "This workspace has no usable index metadata. Reindex the workspace before asking project questions.";
  }

  if (diagnosticCode.includes("index_metadata_exists_but_no_chunks_found")) {
    return "Index metadata exists, but no context chunks were found in the active vector store. Reindex to rebuild the active retrieval collection.";
  }

  if (diagnosticMessage.includes("not been indexed")) {
    return "The backend reported that this workspace has not been indexed for the active runtime.";
  }

  return null;
}

interface MarkdownBlock {
  id: string;
  type: "paragraph" | "bulletList" | "code";
  lines: string[];
  language?: string;
}

function MarkdownAnswer({ content }: { content: string }) {
  const blocks = parseMarkdownBlocks(content);

  return (
    <div className="markdown-answer">
      {blocks.map((block) => {
        if (block.type === "code") {
          return (
            <div className="markdown-code-block" key={block.id}>
              {block.language ? (
                <span className="markdown-code-language">{block.language}</span>
              ) : null}
              <pre>
                <code>{block.lines.join("\n")}</code>
              </pre>
            </div>
          );
        }

        if (block.type === "bulletList") {
          return (
            <ul key={block.id}>
              {block.lines.map((line, index) => (
                <li key={`${block.id}-${index}`}>
                  <InlineMarkdown text={line} />
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={block.id}>
            <InlineMarkdown text={block.lines.join(" ")} />
          </p>
        );
      })}
    </div>
  );
}

function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(`[^`]+`)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("`") && part.endsWith("`") && part.length > 1) {
          return <code key={index}>{part.slice(1, -1)}</code>;
        }
        return <span key={index}>{part}</span>;
      })}
    </>
  );
}

export function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let bullets: string[] = [];
  let codeLines: string[] = [];
  let codeLanguage: string | undefined;
  let inCodeBlock = false;

  function nextId(type: MarkdownBlock["type"]) {
    return `${type}-${blocks.length}`;
  }

  function flushParagraph() {
    if (paragraph.length === 0) return;
    blocks.push({
      id: nextId("paragraph"),
      type: "paragraph",
      lines: paragraph,
    });
    paragraph = [];
  }

  function flushBullets() {
    if (bullets.length === 0) return;
    blocks.push({
      id: nextId("bulletList"),
      type: "bulletList",
      lines: bullets,
    });
    bullets = [];
  }

  function flushCode() {
    blocks.push({
      id: nextId("code"),
      type: "code",
      lines: codeLines,
      language: codeLanguage,
    });
    codeLines = [];
    codeLanguage = undefined;
  }

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/g, "");
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushBullets();
        inCodeBlock = true;
        codeLanguage = trimmed.slice(3).trim() || undefined;
        codeLines = [];
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (trimmed.length === 0) {
      flushParagraph();
      flushBullets();
      continue;
    }

    const bulletMatch = trimmed.match(/^[-*•]\s+(.*)$/);
    if (bulletMatch) {
      flushParagraph();
      bullets.push(bulletMatch[1]);
      continue;
    }

    flushBullets();
    paragraph.push(trimmed);
  }

  if (inCodeBlock) {
    flushCode();
  }
  flushParagraph();
  flushBullets();

  return blocks;
}

function AskEmptyState() {
  return (
    <EmptyState
      title="Start a workspace conversation"
      message="Ask a project question to get a local answer with retrieved sources, diagnostics, and session history."
    />
  );
}

function formatLabel(value: string) {
  return value.replaceAll("_", " ");
}

function createHistoryItem(response: WorkspaceQuestionAnswer): AskHistoryItem {
  return {
    id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
    question: response.question,
    answer: response.answer,
    llmLabel: `${response.llm_provider}/${response.llm_model ?? "default"}`,
    sourcesCount: response.sources.length,
    warningsCount: response.quality_warnings?.length ?? 0,
    createdAt: new Date().toISOString(),
    response,
  };
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function isLikelyProjectQuestion(question: string): boolean {
  const words = question.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  return words.some((word) => PROJECT_QUESTION_KEYWORDS.has(word));
}

function formatSourceScore(score: number): string {
  if (score >= 0 && score <= 1) {
    return `${(score * 100).toFixed(1)}%`;
  }
  return score.toFixed(3);
}
