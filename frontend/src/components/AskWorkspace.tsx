import { FormEvent, useEffect, useRef, useState } from "react";

import { askSelectedWorkspace } from "../api/client";
import { CopyButton } from "./CopyButton";
import type {
  RagQualityWarning,
  RagSource,
  WorkspaceQuestionAnswer,
  SkillContextRequest,
} from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusBadge } from "./StatusBadge";
import { getEnabledSkillPresets, getSkillPresetByAssistantMode, type SkillPreferences } from "./skillLibrary";

type SourceSnippetLimit = 3 | 5 | 8 | 10;

interface AskWorkspaceProps {
  workspaceId: string;
  assistantMode: string;
  defaultSourceSnippets: SourceSnippetLimit;
  skillPreferences: SkillPreferences;
  skillProfileSource?: string;
  skillProfileUpdatedAt?: string | null;
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
  "Are there any AI setup issues?",
  "What files are related to Kubernetes or Helm?",
];

const SOURCE_SNIPPET_LIMITS: SourceSnippetLimit[] = [3, 5, 8, 10];

function parseSourceSnippetLimit(value: string): SourceSnippetLimit {
  const numericValue = Number(value);
  return SOURCE_SNIPPET_LIMITS.includes(numericValue as SourceSnippetLimit)
    ? (numericValue as SourceSnippetLimit)
    : 5;
}

export function AskWorkspace({
  workspaceId,
  assistantMode,
  defaultSourceSnippets,
  skillPreferences,
  skillProfileSource = "default",
  skillProfileUpdatedAt = null,
  onAsked,
}: AskWorkspaceProps) {
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState(defaultSourceSnippets);
  const [history, setHistory] = useState<AskHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [cancelMessage, setCancelMessage] = useState<string | null>(null);
  const askAbortControllerRef = useRef<AbortController | null>(null);
  const showGeneralQuestionHint =
    question.trim().length > 0 && !isLikelyProjectQuestion(question);

  useEffect(() => {
    setLimit(defaultSourceSnippets);
  }, [workspaceId, defaultSourceSnippets]);

  async function askQuestion(questionText: string, options: { clearComposer?: boolean } = {}) {
    const trimmedQuestion = questionText.trim();
    if (!trimmedQuestion) {
      setError("Enter a workspace question before asking.");
      return;
    }

    askAbortControllerRef.current?.abort();
    const abortController = new AbortController();
    askAbortControllerRef.current = abortController;
    setLoading(true);
    setError(null);
    setCancelMessage(null);
    try {
      const result = await askSelectedWorkspace(
        workspaceId,
        trimmedQuestion,
        limit,
        buildSkillContext(skillPreferences),
        { signal: abortController.signal },
      );
      const historyItem = createHistoryItem(result);
      setHistory((current) => [historyItem, ...current].slice(0, 12));
      if (options.clearComposer) {
        setQuestion("");
      }
      await onAsked?.();
    } catch (requestError) {
      if (isAbortError(requestError)) {
        setCancelMessage("Stopped waiting for this answer. The backend may still finish the request if it already started.");
      } else {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Could not ask the chosen workspace AI model.",
        );
      }
    } finally {
      if (askAbortControllerRef.current === abortController) {
        askAbortControllerRef.current = null;
        setLoading(false);
      }
    }
  }

  function stopWaitingForAnswer() {
    askAbortControllerRef.current?.abort();
  }

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void askQuestion(question, { clearComposer: true });
  }

  function editQuestion(questionText: string) {
    setQuestion(questionText);
    setError(null);
  }

  const missingChosenAIModel =
    error?.toLowerCase().includes("selected llm") ||
    error?.toLowerCase().includes("select an llm");

  return (
    <div className="ask-workspace ask-workspace-chat ask-workspace-centered">
      <aside className="ask-context-sidebar">
        <AssistantFocusHint
          assistantMode={assistantMode}
          skillPreferences={skillPreferences}
          skillProfileSource={skillProfileSource}
          skillProfileUpdatedAt={skillProfileUpdatedAt}
        />
      </aside>

      <section className="ask-chat-column">
        <ConversationPanel
          history={history}
          loading={loading}
          onAskAgain={(questionText) => void askQuestion(questionText)}
          onClear={() => setHistory([])}
          onEditQuestion={editQuestion}
          onStopWaiting={stopWaitingForAnswer}
        />

        {cancelMessage ? (
          <div className="ask-cancel-message" role="status">
            {cancelMessage}
          </div>
        ) : null}

        {error ? (
          <div className="ask-error ask-error-centered" role="alert">
            <strong>Could not ask workspace</strong>
            <span>{error}</span>
            {missingChosenAIModel ? (
              <span>Select an AI model in the Models tab, then try again.</span>
            ) : null}
          </div>
        ) : null}

        <section className="panel ask-bottom-composer" aria-label="Ask this workspace">
          <form onSubmit={submitQuestion}>
            <div className="ask-bottom-input-row">
              <label className="sr-only" htmlFor="workspace-question">
                Workspace question
              </label>
              <textarea
                id="workspace-question"
                placeholder="Ask about this project, code, infrastructure, CI/CD, or setup..."
                rows={2}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
              />
              <button
                className="primary-button ask-send-button"
                type="submit"
                disabled={loading || question.trim().length === 0}
              >
                {loading ? "Thinking..." : "Ask"}
              </button>
              {loading ? (
                <button className="secondary-action ask-stop-button" type="button" onClick={stopWaitingForAnswer}>
                  Stop
                </button>
              ) : null}
            </div>

            <div className="ask-bottom-meta-row">
              <span>Nothing happens until you press Ask. Sources stay attached to the answer.</span>
              <label>
                Source snippets
                <select
                  value={limit}
                  onChange={(event) => setLimit(parseSourceSnippetLimit(event.target.value))}
                >
                  {SOURCE_SNIPPET_LIMITS.map((snippetLimit) => (
                    <option key={snippetLimit} value={snippetLimit}>
                      {snippetLimit}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            {showGeneralQuestionHint ? (
              <p className="ask-question-hint ask-question-hint-centered">
                Workspace Ask works best with project, code, infrastructure, CI/CD, or configuration questions.
              </p>
            ) : null}

            <div className="ask-example-strip" aria-label="Example questions">
              {EXAMPLE_QUESTIONS.slice(0, 4).map((example) => (
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
          </form>
        </section>
      </section>
    </div>
  );
}

function ConversationPanel({
  history,
  loading,
  onAskAgain,
  onClear,
  onEditQuestion,
  onStopWaiting,
}: {
  history: AskHistoryItem[];
  loading: boolean;
  onAskAgain: (question: string) => void;
  onClear: () => void;
  onEditQuestion: (question: string) => void;
  onStopWaiting: () => void;
}) {
  const chronologicalHistory = [...history].reverse();

  if (history.length === 0) {
    return (
      <section className="ask-conversation-panel">
        <AskEmptyState />
      </section>
    );
  }

  return (
    <section className="ask-conversation-panel" aria-live="polite">
      <div className="panel ask-conversation-header">
        <div>
          <p className="eyebrow">Current conversation</p>
          <h2>Workspace chat</h2>
          <p>
            Questions and answers stay in this browser tab. Copy answers, edit a
            question, or ask again without changing workspace setup.
          </p>
        </div>
        <div className="ask-conversation-actions">
          <span className="panel-count">{history.length}</span>
          <button className="secondary-button" type="button" onClick={onClear}>
            Clear
          </button>
        </div>
      </div>

      <div className="ask-message-list">
        {chronologicalHistory.map((item) => (
          <ConversationTurn
            item={item}
            key={item.id}
            onAskAgain={onAskAgain}
            onEditQuestion={onEditQuestion}
          />
        ))}
        {loading ? (
          <article className="ask-message-row is-assistant">
            <div className="ask-avatar">AI</div>
            <div className="ask-message-bubble assistant-bubble is-loading">
              <span>Thinking with workspace context...</span>
            </div>
          </article>
        ) : null}
      </div>
    </section>
  );
}

function ConversationTurn({
  item,
  onAskAgain,
  onEditQuestion,
}: {
  item: AskHistoryItem;
  onAskAgain: (question: string) => void;
  onEditQuestion: (question: string) => void;
}) {
  return (
    <article className="ask-conversation-turn">
      <div className="ask-message-row is-user">
        <div className="ask-message-bubble user-bubble">
          <span className="ask-message-label">You</span>
          <p>{item.question}</p>
          <div className="ask-message-actions">
            <button
              className="text-button"
              type="button"
              onClick={() => onEditQuestion(item.question)}
            >
              Edit question
            </button>
            <button
              className="text-button"
              type="button"
              onClick={() => onAskAgain(item.question)}
            >
              Ask again
            </button>
          </div>
        </div>
      </div>

      <AnswerResult answer={item.response} createdAt={item.createdAt} />
    </article>
  );
}

function AnswerResult({
  answer,
  createdAt,
}: {
  answer: WorkspaceQuestionAnswer;
  createdAt: string;
}) {
  const warnings = answer.quality_warnings ?? [];
  const reindexReason = getAskReindexReason(answer);
  const isMissingSourcePaths = warnings.some(
    (warning) => warning.code === "answer_missing_source_paths",
  );

  return (
    <div className="ask-message-row is-assistant">
      <div className="ask-avatar">AI</div>
      <div className="ask-assistant-stack">
        <article className="ask-message-bubble assistant-bubble">
          <div className="assistant-bubble-header">
            <div>
              <span className="ask-message-label">AI Private Workspace</span>
              <small>
                {answer.llm_provider}/{answer.llm_model ?? "default"} · {formatTime(createdAt)}
              </small>
            </div>
            <CopyButton text={answer.answer} label="answer" />
          </div>
          <div className="answer-content">
            {answer.answer ? (
              <MarkdownAnswer content={answer.answer} />
            ) : (
              "The chosen AI model returned an empty answer."
            )}
          </div>
          <div className="answer-stats">
            <span>
              <strong>{answer.used_context_chunks}</strong> context pieces
            </span>
            <span>
              <strong>{answer.sources.length}</strong> sources
            </span>
          </div>
          <LLMUsageSummary answer={answer} />
          <AskSkillProfileAuditSummary answer={answer} />
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
      </div>
    </div>
  );
}


function AskSkillProfileAuditSummary({ answer }: { answer: WorkspaceQuestionAnswer }) {
  const profile = answer.skill_profile;
  if (!profile) {
    return null;
  }

  const sourceLabel = profile.source === "saved"
    ? "Workspace saved profile"
    : profile.source === "request"
      ? "Temporary request guidance"
      : "Default workspace profile";
  const skills = profile.active_skills.length > 0
    ? profile.active_skills.join(" + ")
    : "No active skill guidance";

  return (
    <div className="ask-skill-audit" aria-label="Ask skill profile audit">
      <span title="Skill profile source">{sourceLabel}</span>
      <span title="Active skill guidance">{skills}</span>
      <span title="Guidance items">{profile.guidance_count} guidance item{profile.guidance_count === 1 ? "" : "s"}</span>
      {profile.updated_at ? <span title="Profile saved time">Saved {formatDateTime(profile.updated_at)}</span> : null}
      <span title="Safety note">guidance only; facts need retrieved sources</span>
    </div>
  );
}

function LLMUsageSummary({ answer }: { answer: WorkspaceQuestionAnswer }) {
  const usage = answer.usage;
  const provider = usage?.provider ?? answer.llm_provider;
  const model = usage?.model ?? answer.llm_model ?? "default";

  return (
    <div className="llm-usage-summary" aria-label="LLM usage metrics">
      <span title="Prompt tokens">In {formatMetricNumber(usage?.prompt_tokens)}</span>
      <span title="Answer tokens">Out {formatMetricNumber(usage?.completion_tokens)}</span>
      <span title="Total tokens">Total {formatMetricNumber(usage?.total_tokens)}</span>
      <span title="Latency">{formatLatency(usage?.latency_ms)}</span>
      <span title="Answer speed">{formatSpeed(usage?.tokens_per_second)}</span>
      <span title="Provider and model">{provider}/{model}</span>
      {usage?.estimated ? <span title="Token counts are estimated">est.</span> : null}
    </div>
  );
}

function formatMetricNumber(value: number | null | undefined): string {
  return typeof value === "number" ? value.toLocaleString() : "—";
}

function formatLatency(value: number | null | undefined): string {
  if (typeof value !== "number") {
    return "— ms";
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}s`;
  }
  return `${value}ms`;
}

function formatSpeed(value: number | null | undefined): string {
  return typeof value === "number" ? `${value.toFixed(1)} tok/s` : "— tok/s";
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
  const [showSources, setShowSources] = useState(false);
  const [showAllSources, setShowAllSources] = useState(false);
  const [expandedSourceIds, setExpandedSourceIds] = useState<Set<string>>(
    () => new Set(),
  );
  const topSourceScoreIsLow = sources.length > 0 && sources[0].score < 0.25;
  const visibleSources = showAllSources ? sources : sources.slice(0, 2);
  const hiddenSourcesCount = Math.max(sources.length - visibleSources.length, 0);

  useEffect(() => {
    setShowSources(false);
    setShowAllSources(false);
    setExpandedSourceIds(new Set());
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
    <section className={`panel source-panel ${showSources ? "is-open" : "is-collapsed"}`}>
      <div className="panel-heading source-panel-heading">
        <div>
          <p className="eyebrow">Retrieved context</p>
          <h2>{sources.length > 0 ? `${sources.length} sources attached` : "No sources attached"}</h2>
        </div>
        {sources.length > 0 ? (
          <button
            className="secondary-button source-panel-toggle"
            type="button"
            onClick={() => setShowSources((current) => !current)}
          >
            {showSources ? "Hide sources" : "Show sources"}
          </button>
        ) : null}
      </div>
      {sources.length > 0 && !showSources ? (
        <p className="source-panel-subtitle">
          Sources stay attached to this answer. Open them when you need to verify a claim.
        </p>
      ) : null}
      {sources.length > 0 && showSources ? (
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
              const globalContext = sources.findIndex(
                (candidate) => candidate.chunk_id === source.chunk_id,
              );

              return (
                <article
                  className={globalContext === 0 ? "is-top-source" : undefined}
                  key={source.chunk_id}
                >
                  <div className="source-card-heading">
                    <div>
                      {globalContext === 0 ? (
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
                    {isExpanded ? "Hide" : "Preview"}
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
      ) : null}
      {sources.length === 0 ? (
        <>
          <EmptyState
            title="No sources returned"
            message="Try rebuilding search context or asking a more project-specific question."
            compact
          />
          {!suppressReindexGuidance ? (
            <ReindexGuidance
              workspaceId={workspaceId}
              reason="No sources were returned. If this workspace should have indexed context, rerun indexing manually."
            />
          ) : null}
        </>
      ) : null}
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
        <strong>Prepare search context</strong>
      </div>
      <p>{reason}</p>
      <p>
        If the project has not been scanned yet, run scan first. Then rebuild
        the workspace index.
      </p>
      <CommandGuidanceRow label="Step 1 · scan project" command={scanCommand} />
      <CommandGuidanceRow label="Step 2 · build search context" command={indexCommand} />
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
    return "This workspace has no usable search context yet. Scan the project, then build the search context before asking questions.";
  }

  if (diagnosticCode.includes("index_metadata_exists_but_no_chunks_found")) {
    return "Search context metadata exists, but no context pieces were found in the current retrieval store. Rebuild search context for the current setup.";
  }

  if (diagnosticMessage.includes("not been indexed")) {
    return "The backend reported that this workspace has no search context for the current setup.";
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



function buildSkillContext(skillPreferences: SkillPreferences): SkillContextRequest[] {
  return getEnabledSkillPresets(skillPreferences)
    .map((preset) => {
      const customInstructions =
        skillPreferences[preset.id]?.customInstructions.trim() ?? "";
      return {
        id: preset.id,
        name: preset.name,
        custom_instructions: customInstructions.slice(0, 1200),
      };
    })
    .filter((skill) => skill.custom_instructions.length > 0)
    .slice(0, 5);
}

function AssistantFocusHint({
  assistantMode,
  skillPreferences,
  skillProfileSource,
  skillProfileUpdatedAt,
}: {
  assistantMode: string;
  skillPreferences: SkillPreferences;
  skillProfileSource: string;
  skillProfileUpdatedAt: string | null;
}) {
  const focus = getAskFocus(assistantMode);
  const activePresets = getEnabledSkillPresets(skillPreferences);
  const activeSkillLabel = activePresets.length > 0
    ? activePresets.map((preset) => preset.shortName).join(" + ")
    : "No extra skills";
  const guidanceSummary = activePresets.length > 0
    ? `${activePresets.length} saved guidance item${activePresets.length === 1 ? "" : "s"}`
    : "No saved guidance enabled";
  const profileLabel = skillProfileSource === "saved" ? "Workspace saved profile" : "Default workspace profile";

  return (
    <section className="panel ask-focus-hint ask-focus-hint-compact">
      <header className="ask-focus-compact-header">
        <div>
          <p className="eyebrow">Assistant focus</p>
          <h2>{focus.badge}</h2>
        </div>
        <span>{focus.badge}</span>
      </header>

      <p className="ask-focus-compact-summary">{focus.shortDescription}</p>

      <div className="ask-focus-compact-rows">
        <div>
          <span>Answer style</span>
          <strong>{focus.badge}</strong>
        </div>
        <div>
          <span>Active skills</span>
          <strong>{activeSkillLabel}</strong>
        </div>
        <div>
          <span>Profile source</span>
          <strong>{profileLabel}</strong>
        </div>
        <div>
          <span>Guidance</span>
          <strong>{guidanceSummary}</strong>
        </div>
      </div>

      <p className="ask-focus-compact-note">
        Saved skills guide the answer style and focus. Project claims still need retrieved sources.
        {skillProfileUpdatedAt ? ` Last saved ${formatDateTime(skillProfileUpdatedAt)}.` : ""}
      </p>
    </section>
  );
}

function getAskFocus(mode: string) {
  const focuses: Record<string, { title: string; description: string; shortDescription: string; badge: string }> = {
    devops: {
      title: "DevOps and platform answers",
      description: "Questions are framed around infrastructure, CI/CD, runtime setup, cloud, and operational context.",
      shortDescription: "Infrastructure, CI/CD, runtime, cloud, and operations.",
      badge: "DevOps",
    },
    developer: {
      title: "Developer answers",
      description: "Questions are framed around code structure, implementation details, dependencies, and tests.",
      shortDescription: "Code structure, implementation, dependencies, and tests.",
      badge: "Code",
    },
    documentation: {
      title: "Documentation answers",
      description: "Questions are framed around README files, architecture notes, onboarding, and clear project summaries.",
      shortDescription: "READMEs, architecture notes, onboarding, and summaries.",
      badge: "Docs",
    },
    support_incident: {
      title: "Incident support answers",
      description: "Questions are framed around symptoms, likely causes, troubleshooting checks, and operational next steps.",
      shortDescription: "Symptoms, likely causes, troubleshooting, and checks.",
      badge: "Support",
    },
    manager_summary: {
      title: "Manager-ready answers",
      description: "Questions are framed around concise summaries, risks, progress, and stakeholder-friendly wording.",
      shortDescription: "Concise summaries, risks, progress, and stakeholder notes.",
      badge: "Summary",
    },
  };

  return focuses[mode] ?? focuses.devops;
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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
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

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}
