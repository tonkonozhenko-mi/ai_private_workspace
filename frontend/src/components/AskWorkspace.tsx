import { FormEvent, useState } from "react";

import { askSelectedWorkspace } from "../api/client";
import type {
  RagQualityWarning,
  RagSource,
  WorkspaceQuestionAnswer,
} from "../api/types";

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
        <section className="panel ask-composer">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Selected workspace LLM</p>
              <h2>Ask about this project</h2>
            </div>
            <span className="status-badge status-available">manual submit</span>
          </div>

          <p className="ask-safety-note">
            Questions are sent only when you press Ask. This does not execute
            commands or change runtime settings.
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
          <h2>Session questions</h2>
        </div>
        <span className="panel-count">{history.length}</span>
      </div>

      <p className="ask-history-note">
        Session history is stored only in this browser tab and is not persisted
        by the frontend.
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
        <p className="empty-panel-state">
          No questions asked in this session yet.
        </p>
      )}
    </section>
  );
}

function AnswerResult({ answer }: { answer: WorkspaceQuestionAnswer }) {
  const warnings = answer.quality_warnings ?? [];

  return (
    <section className="ask-results" aria-live="polite">
      <article className="panel answer-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Answer</p>
            <h2>Workspace response</h2>
          </div>
          <span className="answer-model">
            {answer.llm_provider}/{answer.llm_model ?? "default"}
          </span>
        </div>
        <p className="answer-question">{answer.question}</p>
        <div className="answer-content">
          {answer.answer || "The selected LLM returned an empty answer."}
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
          <span>{formatLabel(answer.diagnostic_code ?? "diagnostic")}</span>
          <p>{answer.diagnostic_message}</p>
        </article>
      ) : null}

      {warnings.length > 0 ? <QualityWarnings warnings={warnings} /> : null}

      <Sources sources={answer.sources} />
    </section>
  );
}

function QualityWarnings({ warnings }: { warnings: RagQualityWarning[] }) {
  return (
    <section className="panel quality-warnings">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Deterministic guardrails</p>
          <h2>Quality warnings</h2>
        </div>
        <span className="panel-count">{warnings.length}</span>
      </div>
      <div className="quality-warning-list">
        {warnings.map((warning, index) => (
          <article key={`${warning.code}-${index}`}>
            <span className={`status-badge status-${warning.severity}`}>
              {formatLabel(warning.severity)}
            </span>
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

function Sources({ sources }: { sources: RagSource[] }) {
  return (
    <section className="panel source-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Retrieved context</p>
          <h2>Sources</h2>
        </div>
        <span className="panel-count">{sources.length}</span>
      </div>
      {sources.length > 0 ? (
        <div className="source-list">
          {sources.map((source) => (
            <article key={source.chunk_id}>
              <div>
                <strong>{source.source_path}</strong>
                <span>{source.score.toFixed(3)} score</span>
              </div>
              <p>{source.preview}</p>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-panel-state">
          No context sources were returned. Review the diagnostic message or
          index status before asking again.
        </p>
      )}
    </section>
  );
}

function AskEmptyState() {
  return (
    <section className="panel ask-empty-state">
      <p className="eyebrow">No question submitted</p>
      <h2>Answers and sources will appear here</h2>
      <p>
        The selected workspace LLM is used only after an explicit Ask submit.
        Retrieved source previews make the answer easier to verify.
      </p>
    </section>
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
