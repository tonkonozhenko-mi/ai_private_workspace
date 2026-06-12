import { FormEvent, useEffect, useRef, useState } from "react";

import {
  askSelectedWorkspace,
  createWorkspaceConversation,
  deleteWorkspaceAnswerNote,
  deleteWorkspaceConversation,
  exportWorkspaceConversation,
  getConversationContextPreview,
  getWorkspaceConversation,
  listWorkspaceAnswerNotes,
  listWorkspaceConversations,
  updateWorkspaceAnswerNote,
  updateWorkspaceAnswerNotePinned,
  updateWorkspaceConversationArchived,
  updateWorkspaceConversationPinned,
  saveConversationAnswerNote,
  updateWorkspaceConversationTitle,
} from "../api/client";
import { CopyButton } from "./CopyButton";
import type {
  RagQualityWarning,
  RagSource,
  WorkspaceQuestionAnswer,
  SkillContextRequest,
  ConversationAnswerNote,
  ConversationContextPreview,
  WorkspaceConversation,
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
  const [conversations, setConversations] = useState<WorkspaceConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [conversationSearch, setConversationSearch] = useState("");
  const [answerNoteSearch, setAnswerNoteSearch] = useState("");
  const [answerNotesPinnedOnly, setAnswerNotesPinnedOnly] = useState(false);
  const [answerNotes, setAnswerNotes] = useState<ConversationAnswerNote[]>([]);
  const [conversationContextPreview, setConversationContextPreview] = useState<ConversationContextPreview | null>(null);
  const [conversationStatus, setConversationStatus] = useState<string | null>(null);
  const [showArchivedConversations, setShowArchivedConversations] = useState(false);
  const [pinnedOnlyConversations, setPinnedOnlyConversations] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [cancelMessage, setCancelMessage] = useState<string | null>(null);
  const askAbortControllerRef = useRef<AbortController | null>(null);
  const showGeneralQuestionHint =
    question.trim().length > 0 && !isLikelyProjectQuestion(question);

  useEffect(() => {
    setLimit(defaultSourceSnippets);
  }, [workspaceId, defaultSourceSnippets]);

  useEffect(() => {
    let cancelled = false;

    async function initializeAskState() {
      setHistory([]);
      setActiveConversationId(null);
      setConversationSearch("");
      setShowArchivedConversations(false);
      setPinnedOnlyConversations(false);
      setAnswerNoteSearch("");
      setAnswerNotesPinnedOnly(false);
      setConversationContextPreview(null);

      const [conversationItems] = await Promise.all([
        refreshConversations({ search: "", includeArchived: false, pinnedOnly: false }),
        refreshAnswerNotes({ search: "", pinnedOnly: false }),
      ]);

      const latestConversation = conversationItems[0];
      if (!cancelled && latestConversation) {
        await openConversation(latestConversation.id);
      }
    }

    void initializeAskState();

    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void refreshConversations();
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [conversationSearch, showArchivedConversations, pinnedOnlyConversations]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void refreshAnswerNotes();
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [answerNoteSearch, answerNotesPinnedOnly]);

  async function refreshConversations(
    options: { search?: string; includeArchived?: boolean; pinnedOnly?: boolean } = {},
  ): Promise<WorkspaceConversation[]> {
    try {
      const items = await listWorkspaceConversations(workspaceId, {
        search: options.search ?? conversationSearch,
        includeArchived: options.includeArchived ?? showArchivedConversations,
        pinnedOnly: options.pinnedOnly ?? pinnedOnlyConversations,
      });
      setConversations(items);
      return items;
    } catch {
      setConversations([]);
      return [];
    }
  }

  async function refreshAnswerNotes(
    options: { search?: string; pinnedOnly?: boolean } = {},
  ): Promise<ConversationAnswerNote[]> {
    try {
      const notes = await listWorkspaceAnswerNotes(workspaceId, {
        search: options.search ?? answerNoteSearch,
        pinnedOnly: options.pinnedOnly ?? answerNotesPinnedOnly,
      });
      setAnswerNotes(notes);
      return notes;
    } catch {
      setAnswerNotes([]);
      return [];
    }
  }

  async function exportConversation(conversationId: string, format: "markdown" | "text" | "json" = "markdown") {
    setConversationLoading(true);
    setConversationStatus(null);
    setError(null);
    try {
      const exportedConversation = await exportWorkspaceConversation(workspaceId, conversationId, format);
      downloadTextFile(exportedConversation.filename, exportedConversation.content);
      setConversationStatus(`Exported ${exportedConversation.filename}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not export conversation.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function saveAnswerNote(answer: WorkspaceQuestionAnswer) {
    const conversationId = answer.conversation_id;
    const messageId = answer.conversation_message_id;
    if (!conversationId || !messageId) {
      setError("This answer cannot be saved as a note because message metadata is missing.");
      return;
    }
    setConversationLoading(true);
    setConversationStatus(null);
    setError(null);
    try {
      await saveConversationAnswerNote(workspaceId, conversationId, messageId, {
        title: answer.question.slice(0, 90) || "Saved answer note",
      });
      await refreshAnswerNotes();
      setConversationStatus("Saved answer note");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save answer note.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function editAnswerNote(note: ConversationAnswerNote) {
    const nextTitle = window.prompt("Edit note title", note.title);
    if (nextTitle === null || nextTitle.trim().length === 0) {
      return;
    }
    const nextContent = window.prompt("Edit note content", note.content);
    if (nextContent === null || nextContent.trim().length === 0) {
      return;
    }
    setConversationLoading(true);
    setConversationStatus(null);
    setError(null);
    try {
      await updateWorkspaceAnswerNote(workspaceId, note.id, {
        title: nextTitle.trim(),
        content: nextContent.trim(),
      });
      await refreshAnswerNotes();
      setConversationStatus("Updated answer note");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update answer note.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function toggleAnswerNotePinned(noteId: string, pinned: boolean) {
    setConversationLoading(true);
    setConversationStatus(null);
    setError(null);
    try {
      await updateWorkspaceAnswerNotePinned(workspaceId, noteId, pinned);
      await refreshAnswerNotes();
      setConversationStatus(pinned ? "Pinned answer note" : "Unpinned answer note");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update answer note pin state.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function previewConversationContext(conversationId: string) {
    setConversationLoading(true);
    setConversationStatus(null);
    setError(null);
    try {
      const preview = await getConversationContextPreview(workspaceId, conversationId);
      setConversationContextPreview(preview);
      setConversationStatus("Prepared conversation context preview");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not prepare conversation context preview.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function deleteAnswerNote(noteId: string) {
    setConversationLoading(true);
    setConversationStatus(null);
    setError(null);
    try {
      await deleteWorkspaceAnswerNote(workspaceId, noteId);
      await refreshAnswerNotes();
      setConversationStatus("Deleted answer note");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not delete answer note.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function startNewConversation() {
    setConversationLoading(true);
    setError(null);
    try {
      const conversation = await createWorkspaceConversation(workspaceId, "New conversation");
      setActiveConversationId(conversation.id);
      setHistory([]);
      await refreshConversations();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create conversation.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function renameConversation(conversationId: string, currentTitle: string) {
    const nextTitle = window.prompt("Rename this conversation", currentTitle);
    if (nextTitle === null || nextTitle.trim().length === 0) {
      return;
    }
    setConversationLoading(true);
    setError(null);
    try {
      await updateWorkspaceConversationTitle(workspaceId, conversationId, nextTitle.trim());
      await refreshConversations();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not rename conversation.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function openConversation(conversationId: string) {
    setConversationLoading(true);
    setError(null);
    try {
      const conversation = await getWorkspaceConversation(workspaceId, conversationId);
      setActiveConversationId(conversation.id);
      setHistory(conversationToHistory(conversation));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not open conversation.");
    } finally {
      setConversationLoading(false);
    }
  }


  async function toggleConversationPinned(conversationId: string, pinned: boolean) {
    setConversationLoading(true);
    setError(null);
    try {
      await updateWorkspaceConversationPinned(workspaceId, conversationId, pinned);
      await refreshConversations();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update conversation pin state.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function toggleConversationArchived(conversationId: string, archived: boolean) {
    setConversationLoading(true);
    setError(null);
    try {
      await updateWorkspaceConversationArchived(workspaceId, conversationId, archived);
      if (archived && activeConversationId === conversationId) {
        setActiveConversationId(null);
        setHistory([]);
      }
      await refreshConversations();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not update conversation archive state.");
    } finally {
      setConversationLoading(false);
    }
  }

  async function removeConversation(conversationId: string) {
    setConversationLoading(true);
    setError(null);
    try {
      await deleteWorkspaceConversation(workspaceId, conversationId);
      if (activeConversationId === conversationId) {
        setActiveConversationId(null);
        setHistory([]);
      }
      await refreshConversations();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not delete conversation.");
    } finally {
      setConversationLoading(false);
    }
  }

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
        { signal: abortController.signal, conversationId: activeConversationId },
      );
      const historyItem = createHistoryItem(result);
      setActiveConversationId(result.conversation_id ?? activeConversationId);
      setHistory((current) => [historyItem, ...current].slice(0, 50));
      await refreshConversations();
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
          conversations={conversations}
          activeConversationId={activeConversationId}
          conversationLoading={conversationLoading}
          conversationSearch={conversationSearch}
          answerNotes={answerNotes}
          answerNoteSearch={answerNoteSearch}
          answerNotesPinnedOnly={answerNotesPinnedOnly}
          conversationContextPreview={conversationContextPreview}
          conversationStatus={conversationStatus}
          showArchivedConversations={showArchivedConversations}
          pinnedOnlyConversations={pinnedOnlyConversations}
          onAskAgain={(questionText) => void askQuestion(questionText)}
          onClear={() => setHistory([])}
          onEditQuestion={editQuestion}
          onStopWaiting={stopWaitingForAnswer}
          onNewConversation={() => void startNewConversation()}
          onOpenConversation={(conversationId) => void openConversation(conversationId)}
          onRenameConversation={(conversationId, currentTitle) => void renameConversation(conversationId, currentTitle)}
          onDeleteConversation={(conversationId) => void removeConversation(conversationId)}
          onExportConversation={(conversationId, format) => void exportConversation(conversationId, format)}
          onSaveAnswerNote={(answer) => void saveAnswerNote(answer)}
          onDeleteAnswerNote={(noteId) => void deleteAnswerNote(noteId)}
          onEditAnswerNote={(note) => void editAnswerNote(note)}
          onToggleAnswerNotePinned={(noteId, pinned) => void toggleAnswerNotePinned(noteId, pinned)}
          onSearchAnswerNotes={setAnswerNoteSearch}
          onToggleAnswerNotesPinnedOnly={setAnswerNotesPinnedOnly}
          onPreviewConversationContext={(conversationId) => void previewConversationContext(conversationId)}
          onTogglePinned={(conversationId, pinned) => void toggleConversationPinned(conversationId, pinned)}
          onToggleArchived={(conversationId, archived) => void toggleConversationArchived(conversationId, archived)}
          onSearch={setConversationSearch}
          onToggleShowArchived={setShowArchivedConversations}
          onTogglePinnedOnly={setPinnedOnlyConversations}
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
  conversations,
  activeConversationId,
  conversationLoading,
  conversationSearch,
  answerNotes,
  answerNoteSearch,
  answerNotesPinnedOnly,
  conversationContextPreview,
  conversationStatus,
  showArchivedConversations,
  pinnedOnlyConversations,
  onAskAgain,
  onClear,
  onEditQuestion,
  onStopWaiting,
  onNewConversation,
  onOpenConversation,
  onRenameConversation,
  onDeleteConversation,
  onExportConversation,
  onSaveAnswerNote,
  onDeleteAnswerNote,
  onEditAnswerNote,
  onToggleAnswerNotePinned,
  onSearchAnswerNotes,
  onToggleAnswerNotesPinnedOnly,
  onPreviewConversationContext,
  onTogglePinned,
  onToggleArchived,
  onSearch,
  onToggleShowArchived,
  onTogglePinnedOnly,
}: {
  history: AskHistoryItem[];
  loading: boolean;
  conversations: WorkspaceConversation[];
  activeConversationId: string | null;
  conversationLoading: boolean;
  conversationSearch: string;
  answerNotes: ConversationAnswerNote[];
  answerNoteSearch: string;
  answerNotesPinnedOnly: boolean;
  conversationContextPreview: ConversationContextPreview | null;
  conversationStatus: string | null;
  showArchivedConversations: boolean;
  pinnedOnlyConversations: boolean;
  onAskAgain: (question: string) => void;
  onClear: () => void;
  onEditQuestion: (question: string) => void;
  onStopWaiting: () => void;
  onNewConversation: () => void;
  onOpenConversation: (conversationId: string) => void;
  onRenameConversation: (conversationId: string, currentTitle: string) => void;
  onDeleteConversation: (conversationId: string) => void;
  onExportConversation: (conversationId: string, format: "markdown" | "text" | "json") => void;
  onSaveAnswerNote: (answer: WorkspaceQuestionAnswer) => void;
  onDeleteAnswerNote: (noteId: string) => void;
  onEditAnswerNote: (note: ConversationAnswerNote) => void;
  onToggleAnswerNotePinned: (noteId: string, pinned: boolean) => void;
  onSearchAnswerNotes: (search: string) => void;
  onToggleAnswerNotesPinnedOnly: (pinnedOnly: boolean) => void;
  onPreviewConversationContext: (conversationId: string) => void;
  onTogglePinned: (conversationId: string, pinned: boolean) => void;
  onToggleArchived: (conversationId: string, archived: boolean) => void;
  onSearch: (search: string) => void;
  onToggleShowArchived: (showArchived: boolean) => void;
  onTogglePinnedOnly: (pinnedOnly: boolean) => void;
}) {
  const chronologicalHistory = [...history].reverse();

  if (history.length === 0) {
    return (
      <section className="ask-conversation-panel">
        <ConversationHistoryBar
          conversations={conversations}
          activeConversationId={activeConversationId}
          loading={conversationLoading}
          search={conversationSearch}
          showArchived={showArchivedConversations}
          pinnedOnly={pinnedOnlyConversations}
          answerNotes={answerNotes}
          answerNoteSearch={answerNoteSearch}
          answerNotesPinnedOnly={answerNotesPinnedOnly}
          conversationContextPreview={conversationContextPreview}
          conversationStatus={conversationStatus}
          onNewConversation={onNewConversation}
          onOpenConversation={onOpenConversation}
          onRenameConversation={onRenameConversation}
          onDeleteConversation={onDeleteConversation}
          onExportConversation={onExportConversation}
          onDeleteAnswerNote={onDeleteAnswerNote}
          onEditAnswerNote={onEditAnswerNote}
          onToggleAnswerNotePinned={onToggleAnswerNotePinned}
          onSearchAnswerNotes={onSearchAnswerNotes}
          onToggleAnswerNotesPinnedOnly={onToggleAnswerNotesPinnedOnly}
          onPreviewConversationContext={onPreviewConversationContext}
          onTogglePinned={onTogglePinned}
          onToggleArchived={onToggleArchived}
          onSearch={onSearch}
          onToggleShowArchived={onToggleShowArchived}
          onTogglePinnedOnly={onTogglePinnedOnly}
        />
        <AskEmptyState />
      </section>
    );
  }

  return (
    <section className="ask-conversation-panel" aria-live="polite">
      <ConversationHistoryBar
        conversations={conversations}
        activeConversationId={activeConversationId}
        loading={conversationLoading}
        search={conversationSearch}
        showArchived={showArchivedConversations}
        pinnedOnly={pinnedOnlyConversations}
        answerNotes={answerNotes}
        answerNoteSearch={answerNoteSearch}
        answerNotesPinnedOnly={answerNotesPinnedOnly}
        conversationContextPreview={conversationContextPreview}
        conversationStatus={conversationStatus}
        onNewConversation={onNewConversation}
        onOpenConversation={onOpenConversation}
        onRenameConversation={onRenameConversation}
        onDeleteConversation={onDeleteConversation}
        onExportConversation={onExportConversation}
        onDeleteAnswerNote={onDeleteAnswerNote}
        onEditAnswerNote={onEditAnswerNote}
        onToggleAnswerNotePinned={onToggleAnswerNotePinned}
        onSearchAnswerNotes={onSearchAnswerNotes}
        onToggleAnswerNotesPinnedOnly={onToggleAnswerNotesPinnedOnly}
        onPreviewConversationContext={onPreviewConversationContext}
        onTogglePinned={onTogglePinned}
        onToggleArchived={onToggleArchived}
        onSearch={onSearch}
        onToggleShowArchived={onToggleShowArchived}
        onTogglePinnedOnly={onTogglePinnedOnly}
      />
      <div className="panel ask-conversation-header">
        <div>
          <p className="eyebrow">Current conversation</p>
          <h2>Workspace chat</h2>
          <p>
            Questions and answers are saved with this workspace. Copy answers, edit a
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
            onSaveAnswerNote={onSaveAnswerNote}
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


function ConversationHistoryBar({
  conversations,
  activeConversationId,
  loading,
  search,
  showArchived,
  pinnedOnly,
  answerNotes,
  answerNoteSearch,
  answerNotesPinnedOnly,
  conversationContextPreview,
  conversationStatus,
  onNewConversation,
  onOpenConversation,
  onRenameConversation,
  onDeleteConversation,
  onExportConversation,
  onDeleteAnswerNote,
  onEditAnswerNote,
  onToggleAnswerNotePinned,
  onSearchAnswerNotes,
  onToggleAnswerNotesPinnedOnly,
  onPreviewConversationContext,
  onTogglePinned,
  onToggleArchived,
  onSearch,
  onToggleShowArchived,
  onTogglePinnedOnly,
}: {
  conversations: WorkspaceConversation[];
  activeConversationId: string | null;
  loading: boolean;
  search: string;
  showArchived: boolean;
  pinnedOnly: boolean;
  answerNotes: ConversationAnswerNote[];
  answerNoteSearch: string;
  answerNotesPinnedOnly: boolean;
  conversationContextPreview: ConversationContextPreview | null;
  conversationStatus: string | null;
  onNewConversation: () => void;
  onOpenConversation: (conversationId: string) => void;
  onRenameConversation: (conversationId: string, currentTitle: string) => void;
  onDeleteConversation: (conversationId: string) => void;
  onExportConversation: (conversationId: string, format: "markdown" | "text" | "json") => void;
  onDeleteAnswerNote: (noteId: string) => void;
  onEditAnswerNote: (note: ConversationAnswerNote) => void;
  onToggleAnswerNotePinned: (noteId: string, pinned: boolean) => void;
  onSearchAnswerNotes: (search: string) => void;
  onToggleAnswerNotesPinnedOnly: (pinnedOnly: boolean) => void;
  onPreviewConversationContext: (conversationId: string) => void;
  onTogglePinned: (conversationId: string, pinned: boolean) => void;
  onToggleArchived: (conversationId: string, archived: boolean) => void;
  onSearch: (search: string) => void;
  onToggleShowArchived: (showArchived: boolean) => void;
  onTogglePinnedOnly: (pinnedOnly: boolean) => void;
}) {
  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) ?? null;

  return (
    <section className="panel conversation-history-panel" aria-label="Saved conversations">
      <div className="panel-heading conversation-history-heading">
        <div>
          <p className="eyebrow">Saved conversations</p>
          <h2>Workspace answer history</h2>
          <p>Conversations persist in the local workspace database and can be reopened later.</p>
        </div>
        <button className="secondary-button" type="button" disabled={loading} onClick={onNewConversation}>
          New conversation
        </button>
      </div>

      <div className="conversation-history-tools">
        <label>
          Search history
          <input
            type="search"
            value={search}
            placeholder="Search title, questions, or answers..."
            onChange={(event) => onSearch(event.target.value)}
          />
        </label>
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={pinnedOnly}
            onChange={(event) => onTogglePinnedOnly(event.target.checked)}
          />
          Pinned only
        </label>
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(event) => onToggleShowArchived(event.target.checked)}
          />
          Show archived
        </label>
      </div>

      {conversations.length === 0 ? (
        <p className="conversation-history-empty">No saved conversations yet. Ask a question to create one.</p>
      ) : (
        <div className="conversation-history-list">
          {conversations.slice(0, 8).map((conversation) => {
            const isActive = conversation.id === activeConversationId;
            return (
              <article className={`conversation-history-item ${isActive ? "is-active" : ""}`} key={conversation.id}>
                <button type="button" onClick={() => onOpenConversation(conversation.id)} disabled={loading}>
                  <strong>{conversation.is_pinned ? "★ " : ""}{conversation.title}</strong>
                  <span>
                    {conversation.user_messages_count} question{conversation.user_messages_count === 1 ? "" : "s"} · {conversation.assistant_messages_count} answer{conversation.assistant_messages_count === 1 ? "" : "s"} · {formatDateTime(conversation.updated_at)}
                    {conversation.is_archived ? " · archived" : ""}
                  </span>
                  {conversation.last_answer_preview ? (
                    <em>{conversation.last_answer_preview}</em>
                  ) : null}
                </button>
                <div className="conversation-history-actions">
                  <button
                    className="text-button"
                    type="button"
                    disabled={loading}
                    onClick={() => onTogglePinned(conversation.id, !conversation.is_pinned)}
                  >
                    {conversation.is_pinned ? "Unpin" : "Pin"}
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    disabled={loading}
                    onClick={() => onExportConversation(conversation.id, "markdown")}
                  >
                    Export md
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    disabled={loading}
                    onClick={() => onExportConversation(conversation.id, "text")}
                  >
                    txt
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    disabled={loading}
                    onClick={() => onExportConversation(conversation.id, "json")}
                  >
                    json
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    disabled={loading}
                    onClick={() => onRenameConversation(conversation.id, conversation.title)}
                  >
                    Rename
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    disabled={loading}
                    onClick={() => onToggleArchived(conversation.id, !conversation.is_archived)}
                  >
                    {conversation.is_archived ? "Restore" : "Archive"}
                  </button>
                  <button
                    className="text-button danger-text-button"
                    type="button"
                    disabled={loading}
                    onClick={() => onDeleteConversation(conversation.id)}
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {conversationStatus ? <p className="conversation-history-status">{conversationStatus}</p> : null}

      {answerNotes.length > 0 ? (
        <AnswerNotesPanel
          notes={answerNotes}
          loading={loading}
          search={answerNoteSearch}
          pinnedOnly={answerNotesPinnedOnly}
          onSearch={onSearchAnswerNotes}
          onTogglePinnedOnly={onToggleAnswerNotesPinnedOnly}
          onEditAnswerNote={onEditAnswerNote}
          onToggleAnswerNotePinned={onToggleAnswerNotePinned}
          onDeleteAnswerNote={onDeleteAnswerNote}
        />
      ) : null}

      {activeConversation ? (
        <div className="conversation-context-actions">
          <button
            className="secondary-button"
            type="button"
            disabled={loading}
            onClick={() => onPreviewConversationContext(activeConversation.id)}
          >
            Prepare context preview
          </button>
          <span>This prepares reusable context only. It does not inject history into Ask automatically.</span>
        </div>
      ) : null}

      {conversationContextPreview ? (
        <ConversationContextPreviewCard preview={conversationContextPreview} />
      ) : null}

      {activeConversation ? (
        <ConversationDetailsCard conversation={activeConversation} />
      ) : null}
    </section>
  );
}

function AnswerNotesPanel({
  notes,
  loading,
  search,
  pinnedOnly,
  onSearch,
  onTogglePinnedOnly,
  onEditAnswerNote,
  onToggleAnswerNotePinned,
  onDeleteAnswerNote,
}: {
  notes: ConversationAnswerNote[];
  loading: boolean;
  search: string;
  pinnedOnly: boolean;
  onSearch: (search: string) => void;
  onTogglePinnedOnly: (pinnedOnly: boolean) => void;
  onEditAnswerNote: (note: ConversationAnswerNote) => void;
  onToggleAnswerNotePinned: (noteId: string, pinned: boolean) => void;
  onDeleteAnswerNote: (noteId: string) => void;
}) {
  return (
    <section className="answer-notes-panel" aria-label="Reusable answer notes">
      <div>
        <p className="eyebrow">Reusable notes</p>
        <strong>Saved answer snippets</strong>
        <p>Search, pin, edit, and reuse useful AI answers in docs, tickets, or reports.</p>
      </div>
      <div className="conversation-history-tools answer-notes-tools">
        <label>
          Search notes
          <input
            type="search"
            value={search}
            placeholder="Search title, note text, question, or source..."
            onChange={(event) => onSearch(event.target.value)}
          />
        </label>
        <label className="inline-toggle">
          <input
            type="checkbox"
            checked={pinnedOnly}
            onChange={(event) => onTogglePinnedOnly(event.target.checked)}
          />
          Pinned notes only
        </label>
      </div>
      <div className="answer-notes-list">
        {notes.slice(0, 8).map((note) => (
          <article key={note.id} className={`answer-note-card ${note.is_pinned ? "is-pinned" : ""}`}>
            <div>
              <strong>{note.is_pinned ? "★ " : ""}{note.title}</strong>
              <span>{formatDateTime(note.updated_at)}</span>
            </div>
            {note.source_question ? <p><b>Question:</b> {note.source_question}</p> : null}
            {note.source_paths.length > 0 ? (
              <p><b>Sources:</b> {note.source_paths.slice(0, 3).join(" · ")}{note.source_paths.length > 3 ? ` +${note.source_paths.length - 3} more` : ""}</p>
            ) : null}
            <p>{truncateText(note.content, 260)}</p>
            <div className="answer-note-actions">
              <CopyButton text={note.content} label="note" />
              <button
                className="text-button"
                type="button"
                disabled={loading}
                onClick={() => onToggleAnswerNotePinned(note.id, !note.is_pinned)}
              >
                {note.is_pinned ? "Unpin" : "Pin"}
              </button>
              <button
                className="text-button"
                type="button"
                disabled={loading}
                onClick={() => onEditAnswerNote(note)}
              >
                Edit
              </button>
              <button
                className="text-button danger-text-button"
                type="button"
                disabled={loading}
                onClick={() => onDeleteAnswerNote(note.id)}
              >
                Delete note
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ConversationContextPreviewCard({ preview }: { preview: ConversationContextPreview }) {
  return (
    <article className="conversation-context-preview-card" aria-label="Conversation context preview">
      <div>
        <p className="eyebrow">Context preparation</p>
        <strong>{preview.title}</strong>
        <p>{preview.safety_note}</p>
      </div>
      <div className="conversation-detail-grid">
        <span><b>{preview.questions_count}</b> questions</span>
        <span><b>{preview.answers_count}</b> answers</span>
        <span><b>{preview.notes_count}</b> notes</span>
        <span><b>{preview.source_paths.length}</b> source paths</span>
      </div>
      <pre>{preview.reusable_context}</pre>
      <CopyButton text={preview.reusable_context} label="context preview" />
    </article>
  );
}

function ConversationDetailsCard({ conversation }: { conversation: WorkspaceConversation }) {
  const activeSkills = conversation.active_skills.length > 0
    ? conversation.active_skills.join(" + ")
    : "No saved skill guidance captured yet";
  const model = conversation.last_llm_provider
    ? `${conversation.last_llm_provider}/${conversation.last_llm_model ?? "default"}`
    : "No answer yet";

  return (
    <article className="conversation-details-card" aria-label="Conversation details">
      <div>
        <p className="eyebrow">Conversation details</p>
        <strong>{conversation.is_pinned ? "★ " : ""}{conversation.title}</strong>
      </div>
      <div className="conversation-detail-grid">
        <span><b>{conversation.user_messages_count}</b> questions</span>
        <span><b>{conversation.assistant_messages_count}</b> answers</span>
        <span><b>{formatMetricNumber(conversation.total_tokens)}</b> tokens</span>
        <span>{model}</span>
        <span>{conversation.is_archived ? "Archived" : "Active"}</span>
        <span>{conversation.is_pinned ? "Pinned" : "Not pinned"}</span>
      </div>
      {conversation.last_question ? (
        <p><strong>Last question:</strong> {conversation.last_question}</p>
      ) : null}
      <p><strong>Skill profile:</strong> {conversation.last_skill_profile_source ?? "not captured"} · {activeSkills}</p>
    </article>
  );
}

function ConversationTurn({
  item,
  onAskAgain,
  onEditQuestion,
  onSaveAnswerNote,
}: {
  item: AskHistoryItem;
  onAskAgain: (question: string) => void;
  onEditQuestion: (question: string) => void;
  onSaveAnswerNote: (answer: WorkspaceQuestionAnswer) => void;
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

      <AnswerResult answer={item.response} createdAt={item.createdAt} onSaveAnswerNote={onSaveAnswerNote} />
    </article>
  );
}

function AnswerResult({
  answer,
  createdAt,
  onSaveAnswerNote,
}: {
  answer: WorkspaceQuestionAnswer;
  createdAt: string;
  onSaveAnswerNote: (answer: WorkspaceQuestionAnswer) => void;
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
            <div className="answer-header-actions">
              <button
                className="text-button"
                type="button"
                disabled={!answer.conversation_id || !answer.conversation_message_id}
                onClick={() => onSaveAnswerNote(answer)}
              >
                Save note
              </button>
              <CopyButton text={answer.answer} label="answer" />
            </div>
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


function conversationToHistory(conversation: WorkspaceConversation): AskHistoryItem[] {
  const items: AskHistoryItem[] = [];
  for (let index = 0; index < conversation.messages.length; index += 1) {
    const userMessage = conversation.messages[index];
    const assistantMessage = conversation.messages[index + 1];
    if (!userMessage || !assistantMessage || userMessage.role !== "user" || assistantMessage.role !== "assistant") {
      continue;
    }
    const response: WorkspaceQuestionAnswer = {
      workspace_id: conversation.workspace_id,
      conversation_id: conversation.id,
      conversation_message_id: assistantMessage.id,
      question: userMessage.content,
      answer: assistantMessage.content,
      sources: assistantMessage.sources ?? [],
      used_context_chunks: assistantMessage.used_context_chunks,
      llm_provider: assistantMessage.llm_provider ?? "saved",
      llm_model: assistantMessage.llm_model ?? "history",
      diagnostic_code: null,
      diagnostic_message: null,
      quality_warnings: [],
      usage: {
        prompt_tokens: assistantMessage.prompt_tokens,
        completion_tokens: assistantMessage.completion_tokens,
        total_tokens: assistantMessage.total_tokens,
        latency_ms: assistantMessage.latency_ms,
        provider: assistantMessage.llm_provider,
        model: assistantMessage.llm_model,
        estimated: true,
      },
      skill_profile: assistantMessage.skill_profile_source
        ? {
            source: assistantMessage.skill_profile_source,
            profile: assistantMessage.skill_profile ?? "workspace",
            active_skills: assistantMessage.active_skills,
            guidance_count: assistantMessage.guidance_count,
          }
        : null,
    };
    items.unshift({
      id: assistantMessage.id,
      question: userMessage.content,
      answer: assistantMessage.content,
      llmLabel: `${response.llm_provider}/${response.llm_model ?? "default"}`,
      sourcesCount: assistantMessage.sources_count,
      warningsCount: 0,
      createdAt: assistantMessage.created_at,
      response,
    });
  }
  return items;
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

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function truncateText(value: string, limit: number): string {
  const normalized = " ".concat(value).trim().replace(/\s+/g, " ");
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 1)}…`;
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
