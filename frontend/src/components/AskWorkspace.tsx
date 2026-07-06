import { FormEvent, createContext, useContext, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

// Offline syntax highlighting. We use the modular core build and register only a
// curated set of languages so the bundle stays small (no full highlight.js).
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import dockerfile from "highlight.js/lib/languages/dockerfile";
import go from "highlight.js/lib/languages/go";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

for (const [name, lang] of Object.entries({
  bash,
  dockerfile,
  go,
  ini,
  java,
  javascript,
  json,
  markdown,
  python,
  rust,
  sql,
  typescript,
  xml,
  yaml,
})) {
  hljs.registerLanguage(name, lang);
}

// Lets deeply-nested answer rows know whether to show developer-only telemetry
// (token counts, verification notes) without prop-drilling through the chat tree.
const AskDeveloperModeContext = createContext(false);

import {
  askSelectedWorkspace,
  askSelectedWorkspaceStream,
  getRuntimeMemory,
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
  writeWorkspaceFile,
  addProjectMemory,
  recordAnswerRating,
  getAnswerRatingNudges,
  startIndexWorkspaceJob,
  getWorkspaceJob,
} from "../api/client";
import { AnswerFeedback } from "./AnswerFeedback";
import { AnswerNudges } from "./AnswerNudges";
import { AnswerTracePanel } from "./AnswerTracePanel";
import { CopyButton } from "./CopyButton";
import type {
  RagSource,
  WorkspaceQuestionAnswer,
  SkillContextRequest,
  ConversationAnswerNote,
  ConversationContextPreview,
  WorkspaceConversation,
  RuntimeMemory,
} from "../api/types";
import { EmptyState } from "./EmptyState";
import {
  escapeHtml,
  parseMarkdownBlocks,
  tokenizeInline,
  type MarkdownBlock,
} from "../lib/markdown";
import { formatModelLabel, rawModelTitle } from "../lib/modelLabel";
import { formatSourceLabel } from "../lib/sourceLabel";
import { StatusBadge } from "./StatusBadge";
import { SKILL_PRESETS, getEnabledSkillPresets, getSkillPresetByAssistantMode, type CustomSkill, type SkillPreferences } from "./skillLibrary";

type SourceSnippetLimit = 3 | 5 | 8 | 10;

interface AskWorkspaceProps {
  workspaceId: string;
  assistantMode: string;
  defaultSourceSnippets: SourceSnippetLimit;
  skillPreferences: SkillPreferences;
  customSkills: CustomSkill[];
  skillProfileSource?: string;
  skillProfileUpdatedAt?: string | null;
  developerMode?: boolean;
  answerTemperature?: number;
  defaultReasoning?: boolean;
  defaultStreaming?: boolean;
  onAsked?: () => void | Promise<void>;
  onOpenModels?: () => void;
  onOpenOverview?: () => void;
  // A question pushed in from elsewhere (e.g. a dashboard suggested-question
  // chip). The ``nonce`` changes on each push so the same text can be re-sent.
  seedQuestion?: { text: string; nonce: number } | null;
}

interface AskHistoryItem {
  id: string;
  question: string;
  answer: string;
  llmLabel: string;
  sourcesCount: number;
  warningsCount: number;
  createdAt: string;
  attachedFileNames: string[];
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

// Example prompts tailored to the workspace's assistant mode / skill, so the
// suggestions match what the user actually picked (e.g. developer vs devops).
const EXAMPLE_QUESTIONS_BY_MODE: Record<string, string[]> = {
  devops: [
    "How is Terraform backend configured?",
    "Which CI/CD systems are detected?",
    "What files are related to Kubernetes or Helm?",
  ],
  developer: [
    "What does the main module do?",
    "Where are the tests and what do they cover?",
    "Explain the overall architecture of this project.",
  ],
  code: [
    "What does the main module do?",
    "Where are the tests and what do they cover?",
    "Explain the overall architecture of this project.",
  ],
  documentation: [
    "Summarize what this project is about.",
    "How do I set up and run this project?",
    "What are the main components and how do they fit together?",
  ],
  incident_support: [
    "What could cause a failure at startup?",
    "Where are logs and error handling defined?",
    "What are the rollback or recovery steps?",
  ],
  manager: [
    "Give a short summary of this project for a stakeholder.",
    "What are the main risks in this codebase?",
    "What does this project do, in plain terms?",
  ],
  manager_summary: [
    "Give a short summary of this project for a stakeholder.",
    "What are the main risks in this codebase?",
    "What does this project do, in plain terms?",
  ],
  tester: [
    "Which critical flows should I test?",
    "Where is test coverage thin?",
    "What should I re-test after a change here?",
  ],
  business_analyst: [
    "What does this system do for its users?",
    "What are the main entities and flows?",
    "Which integrations and rules matter here?",
  ],
};

function exampleQuestionsForMode(mode: string): string[] {
  return EXAMPLE_QUESTIONS_BY_MODE[mode] ?? EXAMPLE_QUESTIONS.slice(0, 3);
}

const SOURCE_SNIPPET_LIMITS: SourceSnippetLimit[] = [3, 5, 8, 10];

function parseSourceSnippetLimit(value: string): SourceSnippetLimit {
  const numericValue = Number(value);
  return SOURCE_SNIPPET_LIMITS.includes(numericValue as SourceSnippetLimit)
    ? (numericValue as SourceSnippetLimit)
    : 5;
}

type AttachedTextFile = {
  id: string;
  name: string;
  content: string;
  truncated: boolean;
  sizeKb: number;
};

const ATTACHED_FILE_MAX_BYTES = 200 * 1024;

export function AskWorkspace({
  workspaceId,
  assistantMode,
  defaultSourceSnippets,
  skillPreferences,
  customSkills,
  skillProfileSource = "default",
  skillProfileUpdatedAt = null,
  developerMode = false,
  answerTemperature,
  defaultReasoning = false,
  defaultStreaming = true,
  onAsked,
  onOpenModels,
  onOpenOverview,
  seedQuestion = null,
}: AskWorkspaceProps) {
  const [question, setQuestion] = useState("");
  // Developer details are off by default and can be toggled right here on the
  // Ask screen.
  const [devMode, setDevMode] = useState(false);
  // Reasoning / streaming start from the Settings defaults; the per-chat
  // switches (in developer details) still override them for a single message.
  const [reasoning, setReasoning] = useState(defaultReasoning);
  const [streaming, setStreaming] = useState(defaultStreaming);
  const [streamingText, setStreamingText] = useState("");
  // The just-asked question, shown as a user bubble the instant it's sent (so the
  // feed isn't empty and the text doesn't sit in the composer during the wait).
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  // How hard the answer should lean on the project files. "safe" is the
  // everyday default; the stricter modes help weaker local models stay honest.
  const [answerMode, setAnswerMode] = useState<string>("safe");
  // Per-question "answer style" override (dev mode): "" = workspace default.
  // Value is a preset id or a custom-skill id.
  const [skillOverride, setSkillOverride] = useState<string>("");
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
  const [attachedImages, setAttachedImages] = useState<string[]>([]);
  const [attachedFiles, setAttachedFiles] = useState<AttachedTextFile[]>([]);
  const [sessionFiles, setSessionFiles] = useState<AttachedTextFile[]>([]);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const composerRef = useRef<HTMLElement>(null);
  const [composerHeight, setComposerHeight] = useState(0);

  // The composer is sticky at the bottom and overlaps the transcript, so the
  // auto-scroll anchor needs to clear its height. Track it live as it grows
  // (file chips, suggestions, etc.).
  useEffect(() => {
    const node = composerRef.current;
    if (!node) {
      return;
    }
    const update = () => setComposerHeight(node.offsetHeight);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const askAbortControllerRef = useRef<AbortController | null>(null);

  // A suggested question pushed in from a dashboard chip: drop it into the
  // composer (don't auto-send — the user stays in control) and reveal it.
  useEffect(() => {
    if (!seedQuestion || !seedQuestion.text.trim()) {
      return;
    }
    setQuestion(seedQuestion.text);
    const node = composerRef.current;
    if (node) {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
      const field = node.querySelector<HTMLTextAreaElement>("#workspace-question");
      field?.focus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seedQuestion?.nonce]);

  async function handleImageFiles(files: FileList | File[] | null) {
    if (!files || files.length === 0) {
      return;
    }
    const selected = Array.from(files).slice(0, 4);
    const encoded = await Promise.all(
      selected.map(
        (file) =>
          new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              // Keep the full data URL so previews render; the base64 payload is
              // extracted at send time.
              resolve(typeof reader.result === "string" ? reader.result : "");
            };
            reader.onerror = () => reject(reader.error ?? new Error("Could not read image file"));
            reader.readAsDataURL(file);
          }),
      ),
    );
    setAttachedImages((current) => [...current, ...encoded].slice(0, 4));
  }

  // Drag a log/config/source file onto the composer to read its text straight
  // into the question. Images keep going through the vision attachment path.
  async function handleDroppedFiles(files: FileList | File[] | null) {
    if (!files || files.length === 0) {
      return;
    }
    const all = Array.from(files);
    const images = all.filter((file) => file.type.startsWith("image/"));
    const textFiles = all
      .filter((file) => !file.type.startsWith("image/"))
      .slice(0, 4);

    if (images.length > 0) {
      await handleImageFiles(images);
    }
    if (textFiles.length === 0) {
      return;
    }

    const parsed = await Promise.all(
      textFiles.map(async (file): Promise<AttachedTextFile | null> => {
        const truncated = file.size > ATTACHED_FILE_MAX_BYTES;
        const slice = truncated ? file.slice(0, ATTACHED_FILE_MAX_BYTES) : file;
        let content = "";
        try {
          content = await slice.text();
        } catch {
          return null;
        }
        return {
          id: `${Date.now()}-${file.name}-${Math.random().toString(36).slice(2, 8)}`,
          name: file.name,
          content,
          truncated,
          sizeKb: Math.max(1, Math.round(file.size / 1024)),
        };
      }),
    );

    const readable = parsed.filter((file): file is AttachedTextFile => file !== null);
    if (readable.length > 0) {
      setAttachedFiles((current) => [...current, ...readable].slice(0, 6));
    }
  }
  const showGeneralQuestionHint =
    question.trim().length > 0 && !isLikelyProjectQuestion(question);

  useEffect(() => {
    setLimit(defaultSourceSnippets);
  }, [workspaceId, defaultSourceSnippets]);

  useEffect(() => {
    let cancelled = false;

    async function initializeAskState() {
      setHistory([]);
      setSessionFiles([]);
      setActiveConversationId(null);
      setConversationSearch("");
      setShowArchivedConversations(false);
      setPinnedOnlyConversations(false);
      setAnswerNoteSearch("");
      setAnswerNotesPinnedOnly(false);
      setConversationContextPreview(null);

      // Start each launch with a fresh chat. Past chats stay available in the
      // "Saved chats & notes" drawer. We intentionally do NOT auto-open the most
      // recent conversation, because re-opening it made every new question append
      // to the same conversation forever, so it grew to show the entire history.
      await Promise.all([
        refreshConversations({ search: "", includeArchived: false, pinnedOnly: false }),
        refreshAnswerNotes({ search: "", pinnedOnly: false }),
      ]);
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

  function startNewConversation() {
    // Start a clean dialog without persisting an empty conversation. The next
    // question creates the conversation on the backend automatically.
    setError(null);
    setHistory([]);
    setActiveConversationId(null);
    setQuestion("");
    setAttachedImages([]);
    setCancelMessage(null);
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
    if (!trimmedQuestion && attachedFiles.length === 0) {
      setError("Enter a workspace question before asking.");
      return;
    }

    // Attached files travel separately so the backend can search them for the
    // relevant parts instead of dumping whole files into the prompt. The typed
    // question stays clean; an empty question gets a sensible default.
    const effectiveQuestion =
      trimmedQuestion || (attachedFiles.length > 0 ? "Analyze the attached file(s)." : "");

    askAbortControllerRef.current?.abort();
    const abortController = new AbortController();
    askAbortControllerRef.current = abortController;
    setLoading(true);
    setError(null);
    setCancelMessage(null);
    setStreamingText("");
    // Show the question in the feed immediately and empty the composer, so the
    // 30–40s wait for a local model doesn't look frozen. Capture the attached
    // files first — the request payload was built above, but sentFiles is read
    // after the await, so grab it before clearing.
    setPendingQuestion(effectiveQuestion);
    const sentFiles = attachedFiles;
    if (options.clearComposer) {
      setQuestion("");
      setAttachedImages([]);
      setAttachedFiles([]);
    }
    try {
      const skillContext =
        devMode && skillOverride
          ? buildSkillContextForOverride(skillOverride, skillPreferences, customSkills)
          : buildSkillContext(skillPreferences);
      const askOptions = {
        signal: abortController.signal,
        conversationId: activeConversationId,
        images: attachedImages.map((image) => {
          const comma = image.indexOf(",");
          return comma >= 0 ? image.slice(comma + 1) : image;
        }),
        temperature: answerTemperature ?? null,
        // Only send the reasoning flag when it's ON. When OFF (the default), we
        // omit it entirely so non-reasoning models aren't asked to think (which
        // on Ollama would trigger a rejected request + retry round-trip).
        think: reasoning ? true : null,
        attachedDocuments: attachedFiles.map((file) => ({
          name: file.name,
          content: file.content,
        })),
        // "safe" is the default and sends nothing, so the prompt is unchanged.
        answerMode: answerMode === "safe" ? null : answerMode,
      };

      let result;
      if (streaming) {
        try {
          result = await askSelectedWorkspaceStream(
            workspaceId,
            effectiveQuestion,
            limit,
            skillContext,
            {
              ...askOptions,
              onToken: (text) =>
                setStreamingText((current) => current + text),
            },
          );
        } catch (streamError) {
          if (isAbortError(streamError)) {
            throw streamError;
          }
          // Streaming failed (e.g. backend without SSE support) — fall back to
          // a normal request so the user still gets an answer.
          setStreamingText("");
          result = await askSelectedWorkspace(
            workspaceId,
            effectiveQuestion,
            limit,
            skillContext,
            askOptions,
          );
        }
      } else {
        result = await askSelectedWorkspace(
          workspaceId,
          effectiveQuestion,
          limit,
          skillContext,
          askOptions,
        );
      }
      const historyItem = createHistoryItem(
        result,
        sentFiles.map((file) => file.name),
      );
      setActiveConversationId(result.conversation_id ?? activeConversationId);
      setHistory((current) => [historyItem, ...current].slice(0, 50));
      if (sentFiles.length > 0) {
        // Remember files used in this chat so they can be reviewed and reused.
        setSessionFiles((current) => {
          const byName = new Map(current.map((file) => [file.name, file]));
          for (const file of sentFiles) {
            byName.set(file.name, file);
          }
          return Array.from(byName.values());
        });
      }
      await refreshConversations();
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
        setStreamingText("");
        setPendingQuestion(null);
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
  const modelRuntimeError =
    error?.toLowerCase().includes("ollama") ||
    error?.toLowerCase().includes("selected local model") ||
    error?.toLowerCase().includes("runtime_unavailable") ||
    error?.toLowerCase().includes("load failed") ||
    error?.toLowerCase().includes("unable to reach");

  return (
    <AskDeveloperModeContext.Provider value={devMode}>
    <div
      className="ask-workspace ask-workspace-chat ask-workspace-centered"
      style={{ "--composer-height": `${composerHeight}px` } as CSSProperties}
    >
      <section className="ask-chat-column">
        <AnswerNudges
          workspaceId={workspaceId}
          onOpenModels={onOpenModels}
          onOpenOverview={onOpenOverview}
        />
        <ConversationPanel
          history={history}
          loading={loading}
          streamingText={streamingText}
          pendingQuestion={pendingQuestion}
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
          <div className="ask-error ask-error-centered ask-actionable-error" role="alert">
            <strong>{modelRuntimeError ? "Selected model is not ready" : "Could not ask workspace"}</strong>
            <span>{friendlyAskError(error)}</span>
            {missingChosenAIModel ? (
              <span>Select an AI model in the Models tab, then try again.</span>
            ) : null}
            {modelRuntimeError ? (
              <span>Open Models, choose a ready local model, or install the selected model and try again. Your chat history is still saved.</span>
            ) : null}
          </div>
        ) : null}

        <section className="panel ask-bottom-composer" aria-label="Ask this workspace" ref={composerRef}>
          <form onSubmit={submitQuestion}>
            <div
              className={`ask-bottom-input-row${isDraggingFile ? " is-drag-over" : ""}`}
              onDragOver={(event) => {
                if (event.dataTransfer?.types?.includes("Files")) {
                  event.preventDefault();
                  setIsDraggingFile(true);
                }
              }}
              onDragLeave={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                  setIsDraggingFile(false);
                }
              }}
              onDrop={(event) => {
                if (event.dataTransfer?.files?.length) {
                  event.preventDefault();
                  setIsDraggingFile(false);
                  void handleDroppedFiles(event.dataTransfer.files);
                }
              }}
            >
              <label className="sr-only" htmlFor="workspace-question">
                Workspace question
              </label>
              <textarea
                id="workspace-question"
                placeholder="Ask anything about this project… (Enter to send · Shift+Enter for a new line)"
                title="You can also drop a log, text file, or image here to ask about it."
                rows={2}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    if (!loading && (question.trim().length > 0 || attachedFiles.length > 0)) {
                      void askQuestion(question, { clearComposer: true });
                    }
                  }
                }}
              />
              {isDraggingFile ? (
                <div className="ask-drop-overlay" aria-hidden="true">
                  Drop to attach — logs &amp; text go into your question, images attach for vision
                </div>
              ) : null}
              <button
                className="primary-button ask-send-button"
                type="submit"
                disabled={loading || (question.trim().length === 0 && attachedFiles.length === 0)}
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
              <span className="ask-privacy-note">Answers stay on your computer, with sources attached.</span>
              <div className="ask-meta-controls">
                <label
                  className="ask-mode"
                  title="How strictly the answer should stick to your project files."
                >
                  <span>Mode</span>
                  <select
                    value={answerMode}
                    onChange={(event) => setAnswerMode(event.target.value)}
                  >
                    <option value="safe">Balanced</option>
                    <option value="sources_only">Only from sources</option>
                    <option value="deep">Deep dive</option>
                    <option value="explain">Explain with sources</option>
                  </select>
                </label>
                {devMode ? (
                  <div className="ask-dev-cluster">
                    <label className="ask-switch" title="Only affects reasoning models (deepseek-r1, qwq…)">
                      <input
                        type="checkbox"
                        checked={reasoning}
                        onChange={(event) => setReasoning(event.target.checked)}
                      />
                      <span className="ask-switch-track" aria-hidden="true">
                        <span className="ask-switch-thumb" />
                      </span>
                      <span className="ask-switch-label">Reasoning</span>
                    </label>
                    <label className="ask-switch" title="Show the answer as it is generated, word by word.">
                      <input
                        type="checkbox"
                        checked={streaming}
                        onChange={(event) => setStreaming(event.target.checked)}
                      />
                      <span className="ask-switch-track" aria-hidden="true">
                        <span className="ask-switch-thumb" />
                      </span>
                      <span className="ask-switch-label">Streaming</span>
                    </label>
                    <label className="ask-snippets" title="Answer style for the next question. Overrides the project's saved skills (this question only).">
                      <span>Style</span>
                      <select
                        value={skillOverride}
                        onChange={(event) => setSkillOverride(event.target.value)}
                      >
                        <option value="">Project default</option>
                        <optgroup label="Built-in">
                          {SKILL_PRESETS.map((preset) => (
                            <option key={preset.id} value={preset.id}>
                              {preset.name}
                            </option>
                          ))}
                        </optgroup>
                        {customSkills.length > 0 ? (
                          <optgroup label="Your skills">
                            {customSkills.map((skill) => (
                              <option key={skill.id} value={skill.id}>
                                {skill.name}
                              </option>
                            ))}
                          </optgroup>
                        ) : null}
                      </select>
                    </label>
                    <label className="ask-snippets" title="How many source snippets to retrieve as context.">
                      <span>Sources</span>
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
                ) : null}
                <label className="ask-switch ask-switch-anchor">
                  <input
                    type="checkbox"
                    checked={devMode}
                    onChange={(event) => setDevMode(event.target.checked)}
                  />
                  <span className="ask-switch-track" aria-hidden="true">
                    <span className="ask-switch-thumb" />
                  </span>
                  <span className="ask-switch-label">Developer details</span>
                </label>
              </div>
            </div>

            <div className="ask-attach-row">
              <label className="ask-attach-button">
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={(event) => {
                    void handleImageFiles(event.target.files);
                    event.target.value = "";
                  }}
                />
                Attach image
              </label>
              <span
                className="ask-attach-hint"
                title="Add a diagram or screenshot to ask about it. Needs a vision model (for example llama3.2-vision); it is sent only to your local AI."
              >
                Needs a vision model · stays local
              </span>
            </div>
            {attachedImages.length > 0 ? (
              <div className="ask-attach-previews" aria-label="Attached images">
                {attachedImages.map((image, index) => (
                  <div key={index} className="ask-attach-thumb">
                    <img src={image} alt={`Attached ${index + 1}`} />
                    <button
                      type="button"
                      aria-label={`Remove attached image ${index + 1}`}
                      onClick={() =>
                        setAttachedImages((current) => current.filter((_, i) => i !== index))
                      }
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            ) : null}

            {attachedFiles.length > 0 ? (
              <div className="ask-file-chips" aria-label="Attached files">
                {attachedFiles.map((file) => (
                  <span key={file.id} className="ask-file-chip">
                    <span className="ask-file-chip-icon" aria-hidden="true">
                      ▤
                    </span>
                    <span className="ask-file-chip-name" title={file.name}>
                      {file.name}
                    </span>
                    <span className="ask-file-chip-size">
                      {file.truncated ? `${Math.round(ATTACHED_FILE_MAX_BYTES / 1024)}KB+` : `${file.sizeKb}KB`}
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove ${file.name}`}
                      onClick={() =>
                        setAttachedFiles((current) => current.filter((item) => item.id !== file.id))
                      }
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>
            ) : null}

            {showGeneralQuestionHint ? (
              <p className="ask-question-hint ask-question-hint-centered">
                Workspace Ask works best with project, code, infrastructure, CI/CD, or configuration questions.
              </p>
            ) : null}

            {history.length === 0 ? (
              <div className="ask-example-strip" aria-label="Example questions">
                {exampleQuestionsForMode(assistantMode).map((example) => (
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
            ) : null}
            {sessionFiles.length > 0 ? (
              <ChatFilesPanel
                files={sessionFiles}
                attachedNames={attachedFiles.map((file) => file.name)}
                onReuse={(reuse) =>
                  setAttachedFiles((current) => {
                    const byName = new Map(
                      current.map((file) => [file.name, file]),
                    );
                    for (const file of reuse) {
                      byName.set(file.name, file);
                    }
                    return Array.from(byName.values());
                  })
                }
                onRemove={(name) =>
                  setSessionFiles((current) =>
                    current.filter((file) => file.name !== name),
                  )
                }
              />
            ) : null}
          </form>
        </section>
      </section>
      <AskScrollButtons />
    </div>
    </AskDeveloperModeContext.Provider>
  );
}

function AskScrollButtons() {
  const scroller = () => document.querySelector<HTMLElement>(".main-content");
  return (
    <div className="ask-scroll-buttons">
      <button
        type="button"
        aria-label="Scroll to top"
        title="Scroll to top"
        onClick={() => scroller()?.scrollTo({ top: 0, behavior: "smooth" })}
      >
        ↑
      </button>
      <button
        type="button"
        aria-label="Scroll to bottom"
        title="Scroll to bottom"
        onClick={() => {
          const el = scroller();
          el?.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
        }}
      >
        ↓
      </button>
    </div>
  );
}

function ConversationPanel({
  history,
  loading,
  streamingText,
  pendingQuestion,
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
  streamingText: string;
  pendingQuestion: string | null;
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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Jump to the newest message (or the "thinking" indicator) whenever a new
  // turn starts or arrives, so the answer is in view without manual scrolling.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [loading, chronologicalHistory.length]);

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
        onClear={onClear}
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
        {loading && pendingQuestion ? (
          <article className="ask-message-row is-user">
            <div className="ask-message-bubble user-bubble">{pendingQuestion}</div>
          </article>
        ) : null}
        {loading ? (
          <article className="ask-message-row is-assistant">
            <img className="ask-avatar-img" src="/avatar-ai-robot-512.png" alt="AI" width={32} height={32} />
            <div className="ask-assistant-stack">
              {streamingText ? (
                <div className="ask-message-bubble assistant-bubble is-streaming">
                  {/* Render markdown as it streams so formatting (lists, code,
                      tables) builds up live instead of flashing in at the end. */}
                  <MarkdownAnswer content={streamingText.replace(/<\/?think>/g, "").trimStart()} />
                  <span className="ask-stream-caret" aria-hidden="true" />
                </div>
              ) : (
                <ThinkingIndicator />
              )}
              <RuntimeMemoryBar active={loading} />
            </div>
          </article>
        ) : null}
        <div ref={messagesEndRef} className="ask-scroll-anchor" aria-hidden="true" />
      </div>
    </section>
  );
}


function ChatFilesPanel({
  files,
  attachedNames,
  onReuse,
  onRemove,
}: {
  files: AttachedTextFile[];
  attachedNames: string[];
  onReuse: (files: AttachedTextFile[]) => void;
  onRemove: (name: string) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (name: string) =>
    setSelected((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : [...current, name],
    );

  const reuseSelected = () => {
    const picked = files.filter((file) => selected.includes(file.name));
    if (picked.length > 0) {
      onReuse(picked);
      setSelected([]);
    }
  };

  return (
    <div className="chat-files" aria-label="Files used in this chat">
      <span className="chat-files-lead">Files in chat</span>
      {files.map((file) => {
        const isSelected = selected.includes(file.name);
        const isAttached = attachedNames.includes(file.name);
        return (
          <span
            key={file.name}
            className={`chat-file-tag${isSelected ? " is-selected" : ""}${isAttached ? " is-attached" : ""}`}
          >
            <button
              type="button"
              className="chat-file-tag-main"
              title={isAttached ? "Attached to your next question" : "Select to re-ask about this file"}
              onClick={() => toggle(file.name)}
            >
              <span className="chat-file-tag-icon" aria-hidden="true">▤</span>
              <span className="chat-file-tag-name">{file.name}</span>
            </button>
            <button
              type="button"
              className="chat-file-tag-x"
              aria-label={`Remove ${file.name} from this chat`}
              title="Remove from this chat"
              onClick={() => onRemove(file.name)}
            >
              &times;
            </button>
          </span>
        );
      })}
      {selected.length > 0 ? (
        <button type="button" className="chat-files-reask" onClick={reuseSelected}>
          Re-ask about {selected.length}
        </button>
      ) : null}
    </div>
  );
}

function formatGb(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

function RuntimeMemoryBar({ active }: { active: boolean }) {
  const [memory, setMemory] = useState<RuntimeMemory | null>(null);

  useEffect(() => {
    if (!active) {
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const next = await getRuntimeMemory();
        if (!cancelled) {
          setMemory(next);
        }
      } catch {
        // Ignore transient errors while polling.
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [active]);

  if (
    !memory ||
    !memory.runtime_reachable ||
    memory.total_ram_bytes <= 0 ||
    memory.models.length === 0
  ) {
    return null;
  }

  const used = memory.loaded_bytes;
  const total = memory.total_ram_bytes;
  const percent = Math.min(100, Math.max(2, Math.round((used / total) * 100)));
  const modelName = memory.models[0]?.name ?? "model";

  return (
    <div
      className="runtime-mem"
      title={`${modelName} is using ${formatGb(used)} of ${formatGb(total)} system RAM`}
      aria-label={`Model memory ${formatGb(used)} of ${formatGb(total)}`}
    >
      <span className="runtime-mem-dot" aria-hidden="true" />
      <span className="runtime-mem-track" aria-hidden="true">
        <span className="runtime-mem-fill" style={{ width: `${percent}%` }} />
      </span>
      <span className="runtime-mem-label">
        {formatGb(used)} <span>/ {formatGb(total)} RAM</span>
      </span>
    </div>
  );
}

// Phase text derived from elapsed time. The backend doesn't stream retrieval
// phases, but a moving label (searching → reading → writing) is far less "stuck"
// than a static "Thinking…" during the 30–40s a local 7B needs before the first
// token. Time thresholds are a heuristic; the label flips to the real streamed
// text the moment a token arrives.
function thinkingPhase(seconds: number): string {
  if (seconds < 4) return "Searching your project files…";
  if (seconds < 9) return "Reading the most relevant parts…";
  return "Writing the answer…";
}

function ThinkingIndicator() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className="ask-message-bubble assistant-bubble is-loading">
      <span>
        <span className="ask-thinking-dot" aria-hidden="true" />
        {thinkingPhase(seconds)} <strong>{seconds}s</strong>
      </span>
      {seconds >= 10 ? (
        <span className="ask-thinking-note">
          Running locally on your CPU, so this can take a while —
          the answer appears here when it's ready. Press Stop to cancel.
        </span>
      ) : null}
    </div>
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
  onClear,
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
  onClear?: () => void;
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
  const developerMode = useContext(AskDeveloperModeContext);
  const [open, setOpen] = useState(false);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const activeConversation = conversations.find((conversation) => conversation.id === activeConversationId) ?? null;

  // Close the per-row "⋯" menu when clicking anywhere outside of it.
  useEffect(() => {
    if (!menuFor) {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target?.closest(".conversation-row-menu-wrap")) {
        setMenuFor(null);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [menuFor]);

  return (
    <div className="ask-chats-zone">
      <div className="ask-chats-toolbar">
        <button
          className="ask-new-chat-button"
          type="button"
          disabled={loading}
          onClick={() => {
            onNewConversation();
            setOpen(false);
            setMenuFor(null);
          }}
        >
          + New chat
        </button>
        <button
          className={`ask-saved-toggle ${open ? "is-open" : ""}`}
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          Saved chats &amp; notes
          <span className="ask-saved-chevron" aria-hidden="true">{open ? "▴" : "▾"}</span>
        </button>
        {onClear ? (
          <button
            className="ask-clear-chat-button"
            type="button"
            disabled={loading}
            onClick={onClear}
            title="Clear the current chat"
          >
            Clear chat
          </button>
        ) : null}
      </div>

      {open ? (
        <section className="conversation-history-panel" aria-label="Saved conversations">
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
                <button
                  type="button"
                  className="conversation-open"
                  onClick={() => {
                    onOpenConversation(conversation.id);
                    setOpen(false);
                    setMenuFor(null);
                  }}
                  disabled={loading}
                >
                  <strong>{conversation.is_pinned ? "★ " : ""}{conversation.title}</strong>
                  <span className="conversation-history-meta">
                    <span>
                      {conversation.user_messages_count} question{conversation.user_messages_count === 1 ? "" : "s"} · {conversation.assistant_messages_count} answer{conversation.assistant_messages_count === 1 ? "" : "s"}
                    </span>
                    <time className="conversation-when">{formatDateTime(conversation.updated_at)}</time>
                    {conversation.is_archived ? <span className="conversation-archived-tag">archived</span> : null}
                  </span>
                  {conversation.last_answer_preview ? (
                    <em>{conversation.last_answer_preview}</em>
                  ) : null}
                </button>
                <div className="conversation-row-menu-wrap">
                  <button
                    type="button"
                    className="conversation-menu-button"
                    aria-label="Conversation actions"
                    aria-expanded={menuFor === conversation.id}
                    disabled={loading}
                    onClick={() => setMenuFor(menuFor === conversation.id ? null : conversation.id)}
                  >
                    ⋯
                  </button>
                  {menuFor === conversation.id ? (
                    <div className="conversation-row-menu" role="menu">
                      <button type="button" role="menuitem" onClick={() => { onTogglePinned(conversation.id, !conversation.is_pinned); setMenuFor(null); }}>
                        {conversation.is_pinned ? "Unpin" : "Pin"}
                      </button>
                      <button type="button" role="menuitem" onClick={() => { onRenameConversation(conversation.id, conversation.title); setMenuFor(null); }}>
                        Rename
                      </button>
                      <button type="button" role="menuitem" onClick={() => { onExportConversation(conversation.id, "markdown"); setMenuFor(null); }}>
                        Export Markdown
                      </button>
                      <button type="button" role="menuitem" onClick={() => { onExportConversation(conversation.id, "text"); setMenuFor(null); }}>
                        Export text
                      </button>
                      <button type="button" role="menuitem" onClick={() => { onExportConversation(conversation.id, "json"); setMenuFor(null); }}>
                        Export JSON
                      </button>
                      <button type="button" role="menuitem" onClick={() => { onToggleArchived(conversation.id, !conversation.is_archived); setMenuFor(null); }}>
                        {conversation.is_archived ? "Restore" : "Archive"}
                      </button>
                      <button type="button" role="menuitem" className="danger-text-button" onClick={() => { onDeleteConversation(conversation.id); setMenuFor(null); }}>
                        Delete
                      </button>
                    </div>
                  ) : null}
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

      {developerMode && activeConversation ? (
        <div className="conversation-context-actions">
          <button
            className="text-button"
            type="button"
            disabled={loading}
            onClick={() => onPreviewConversationContext(activeConversation.id)}
          >
            Prepare context preview
          </button>
          <span>This prepares reusable context only. It does not inject history into Ask automatically.</span>
        </div>
      ) : null}

      {developerMode && conversationContextPreview ? (
        <ConversationContextPreviewCard preview={conversationContextPreview} />
      ) : null}

      {developerMode && activeConversation ? (
        <ConversationDetailsCard conversation={activeConversation} />
      ) : null}
        </section>
      ) : null}
    </div>
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
              <p><b>Sources:</b> {note.source_paths.slice(0, 3).map(formatSourceLabel).join(" · ")}{note.source_paths.length > 3 ? ` +${note.source_paths.length - 3} more` : ""}</p>
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
    ? formatModelLabel(conversation.last_llm_provider, conversation.last_llm_model)
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
          <p>{item.question}</p>
          {item.attachedFileNames.length > 0 ? (
            <div className="ask-message-files" aria-label="Attached files">
              {item.attachedFileNames.map((name) => (
                <span key={name} className="ask-message-file-chip" title={name}>
                  <span className="ask-message-file-icon" aria-hidden="true">▤</span>
                  {name}
                </span>
              ))}
            </div>
          ) : null}
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
        <img className="ask-avatar-img" src="/avatar-user-pigeon-512.png" alt="You" width={32} height={32} />
      </div>

      <AnswerResult answer={item.response} createdAt={item.createdAt} attachedFileNames={item.attachedFileNames} onSaveAnswerNote={onSaveAnswerNote} />
    </article>
  );
}

function AnswerResult({
  answer,
  createdAt,
  attachedFileNames,
  onSaveAnswerNote,
}: {
  answer: WorkspaceQuestionAnswer;
  createdAt: string;
  attachedFileNames: string[];
  onSaveAnswerNote: (answer: WorkspaceQuestionAnswer) => void;
}) {
  const developerMode = useContext(AskDeveloperModeContext);
  // The verbose "Answer verification" panel (medium/low diagnostics) was removed.
  // We still surface genuinely important, high-severity notices — e.g. "you're on
  // the placeholder test model, answers aren't real" — as a single calm line so
  // the product stays honest about when an answer can't be trusted.
  const highWarnings = (answer.quality_warnings ?? []).filter(
    (warning) => warning.severity === "high",
  );
  const reindexReason = getAskReindexReason(answer);
  const [showFileDraft, setShowFileDraft] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);

  return (
    <div className="ask-message-row is-assistant">
      <img className="ask-avatar-img" src="/avatar-ai-robot-512.png" alt="AI" width={32} height={32} />
      <div className="ask-assistant-stack">
        <article className="ask-message-bubble assistant-bubble">
          <div className="assistant-bubble-header">
            <div>
              <small title={rawModelTitle(answer.llm_provider, answer.llm_model)}>
                {formatModelLabel(answer.llm_provider, answer.llm_model)} · {formatTime(createdAt)}
              </small>
            </div>
            <div className="answer-header-actions">
              <button
                className="answer-icon-button"
                type="button"
                data-tip="Save as note"
                aria-label="Save as note"
                disabled={!answer.conversation_id || !answer.conversation_message_id}
                onClick={() => onSaveAnswerNote(answer)}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                </svg>
              </button>
              <CopyButton text={answer.answer} label="answer" iconOnly />
              <button
                className={`answer-icon-button${showFileDraft ? " is-active" : ""}`}
                type="button"
                data-tip={showFileDraft ? "Close file draft" : "Create file"}
                data-tip-align="end"
                aria-label={showFileDraft ? "Close file draft" : "Create file from this answer"}
                onClick={() => setShowFileDraft((current) => !current)}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6M12 12v6M9 15h6" />
                </svg>
              </button>
            </div>
          </div>
          {(() => {
            const { reasoning, answer: finalAnswer } = extractReasoning(answer.answer);
            return (
              <>
                {reasoning ? (
                  <details className="answer-reasoning">
                    <summary>
                      <span className="answer-reasoning-dot" aria-hidden="true" />
                      Show how the model reasoned
                    </summary>
                    <div className="answer-reasoning-body">
                      <MarkdownAnswer content={reasoning} />
                    </div>
                  </details>
                ) : null}
                <div className="answer-content">
                  {finalAnswer ? (
                    <MarkdownAnswer content={finalAnswer} />
                  ) : reasoning ? (
                    "The model shared its reasoning but no final answer."
                  ) : (
                    "The chosen AI model returned an empty answer."
                  )}
                </div>
              </>
            );
          })()}
          {developerMode ? <AskUsageMetrics answer={answer} /> : null}
        </article>

        {showFileDraft ? (
          <AnswerFileDraft
            workspaceId={answer.workspace_id}
            answer={answer.answer}
            onClose={() => setShowFileDraft(false)}
          />
        ) : null}

        {answer.diagnostic_message ? (
          <article
            className={`ask-diagnostic${
              answer.diagnostic_code === "answered_as_general_conversation"
                ? " is-general-conversation"
                : ""
            }`}
          >
            <span>{formatLabel(answer.diagnostic_code ?? "workspace status")}</span>
            <p>{answer.diagnostic_message}</p>
            {answer.diagnostic_code === "answered_as_general_conversation" &&
            !reindexReason ? (
              <p className="ask-diagnostic-actions">
                Asking about this project? Try rephrasing with names from your
                code, or <RebuildContextButton workspaceId={answer.workspace_id} />
              </p>
            ) : null}
          </article>
        ) : null}

        {reindexReason ? (
          <ReindexGuidance
            workspaceId={answer.workspace_id}
            reason={reindexReason}
          />
        ) : null}

        {highWarnings.length > 0 ? (
          <div className="ask-trust-notice" role="alert">
            {highWarnings.map((warning, index) => (
              <p key={`${warning.code}-${index}`}>{warning.message}</p>
            ))}
          </div>
        ) : null}

        {(answer.project_memory_used ?? 0) > 0 ||
        (answer.project_facts_used ?? 0) > 0 ||
        (answer.project_guardrails_used?.length ?? 0) > 0 ||
        answer.sources.length > 0 ? (
          <button type="button" className="why-answer-btn" onClick={() => setTraceOpen(true)}>
            <span className="wab-icon" aria-hidden="true">?</span>
            How did the AI reach this?
            <span className="wab-meta">
              {answer.project_memory_used ?? 0} note
              {(answer.project_memory_used ?? 0) === 1 ? "" : "s"} · {answer.project_facts_used ?? 0} map fact
              {(answer.project_facts_used ?? 0) === 1 ? "" : "s"}
              {(answer.project_guardrails_used?.length ?? 0) > 0
                ? ` · ${answer.project_guardrails_used?.length} guardrail${
                    (answer.project_guardrails_used?.length ?? 0) === 1 ? "" : "s"
                  }`
                : ""}
            </span>
          </button>
        ) : null}
        {traceOpen ? (
          <AnswerTracePanel
            scope="project"
            memoryUsed={answer.project_memory_used ?? 0}
            factsUsed={answer.project_facts_used ?? 0}
            chunks={answer.used_context_chunks ?? 0}
            files={answer.sources.map((source) => ({
              source_path: source.source_path,
              chunk_id: source.chunk_id,
              score: source.score,
            }))}
            guardrails={answer.project_guardrails_used ?? []}
            memoryDetails={answer.project_memory_details ?? []}
            warnings={answer.quality_warnings ?? []}
            latencyMs={answer.usage?.latency_ms ?? null}
            investigate={{ workspaceId: answer.workspace_id, question: answer.question }}
            onClose={() => setTraceOpen(false)}
          />
        ) : null}

        {answer.sources.length > 0 || attachedFileNames.length > 0 ? (
          <Sources
            workspaceId={answer.workspace_id}
            sources={answer.sources}
            attachedFileNames={attachedFileNames}
            suppressReindexGuidance={reindexReason !== null}
          />
        ) : null}

        {answer.answer.trim().length > 0 && !answer.diagnostic_code ? (
          <AnswerFeedback
            question={answer.question}
            answer={answer.answer}
            onSave={(text, k) => addProjectMemory(answer.workspace_id, text, k)}
            onRate={(verdict) =>
              void recordAnswerRating(answer.workspace_id, {
                verdict,
                llm_model: `${answer.llm_provider}/${answer.llm_model ?? "default"}`,
                context_chunks: answer.used_context_chunks,
              })
            }
          />
        ) : null}
      </div>
    </div>
  );
}

function AnswerFileDraft({
  workspaceId,
  answer,
  onClose,
}: {
  workspaceId: string;
  answer: string;
  onClose: () => void;
}) {
  const [relativePath, setRelativePath] = useState("");
  const [content, setContent] = useState(() => extractFirstCodeBlock(answer) ?? answer);
  const [overwrite, setOverwrite] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function saveFile() {
    if (!relativePath.trim()) {
      setError("Enter a relative path such as docs/generated-overview.md.");
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const result = await writeWorkspaceFile(workspaceId, {
        relative_path: relativePath.trim(),
        content,
        overwrite,
      });
      setMessage(`${result.status === "replaced" ? "Replaced" : "Created"} ${result.relative_path} (${result.bytes_written} bytes).`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Could not save workspace file.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="ask-file-draft" aria-label="Review and create workspace file">
      <div className="ask-file-draft-heading">
        <div>
          <p className="eyebrow">Explicit file change</p>
          <h3>Review before creating a project file</h3>
          <p>The file is written only after you press Create file. Paths outside this workspace are blocked.</p>
        </div>
        <StatusBadge label="Review required" tone="warning" />
      </div>
      <label>
        <span>Relative project path</span>
        <input
          value={relativePath}
          placeholder="docs/generated-overview.md"
          onChange={(event) => setRelativePath(event.target.value)}
        />
      </label>
      <label>
        <span>Exact file content</span>
        <textarea
          rows={12}
          value={content}
          spellCheck={false}
          onChange={(event) => setContent(event.target.value)}
        />
      </label>
      <label className="ask-file-overwrite">
        <input
          type="checkbox"
          checked={overwrite}
          onChange={(event) => setOverwrite(event.target.checked)}
        />
        Allow replacing an existing file after review
      </label>
      <div className="ask-file-draft-actions">
        <button className="primary-button" type="button" disabled={saving} onClick={() => void saveFile()}>
          {saving ? "Saving…" : "Create file"}
        </button>
        <button className="secondary-action" type="button" onClick={onClose}>
          Cancel
        </button>
      </div>
      {message ? <p className="ask-file-message">{message}</p> : null}
      {error ? <p className="ask-file-error" role="alert">{error}</p> : null}
    </section>
  );
}

function extractFirstCodeBlock(value: string): string | null {
  const match = value.match(/```(?:[a-zA-Z0-9_-]+)?\s*\n([\s\S]*?)```/);
  return match?.[1]?.trimEnd() ?? null;
}


// Developer-mode answer metrics. Labelled so each value is self-explanatory, and
// trimmed to what actually carries meaning: token usage, speed, latency, and how
// much retrieved context fed the model. (The old skill-profile audit row and the
// redundant model-id pill were removed — the model is already in the header.)
function AskUsageMetrics({ answer }: { answer: WorkspaceQuestionAnswer }) {
  const usage = answer.usage;
  const total = usage?.total_tokens ?? null;
  const window = usage?.context_window ?? null;
  const windowPct =
    total != null && window ? Math.min(100, Math.round((total / window) * 100)) : null;
  const stats: { label: string; value: string; title: string }[] = [
    {
      label: "Tokens in",
      value: formatMetricNumber(usage?.prompt_tokens),
      title: "Tokens sent to the model — your question plus the retrieved project context",
    },
    {
      label: "Tokens out",
      value: formatMetricNumber(usage?.completion_tokens),
      title: "Tokens the model generated for this answer",
    },
    {
      label: window ? "Context used" : "Total",
      value:
        window && total != null
          ? `${formatMetricNumber(total)} / ${formatMetricNumber(window)}${windowPct != null ? ` · ${windowPct}%` : ""}`
          : formatMetricNumber(total),
      title: window
        ? "Tokens used this request vs the model's context window — the most it can hold at once. When it fills up, retrieved context gets dropped."
        : "Prompt tokens + answer tokens",
    },
    {
      label: "Speed",
      value: formatSpeed(usage?.tokens_per_second),
      title: "Generation speed, in tokens per second",
    },
    {
      label: "Time",
      value: formatLatency(usage?.latency_ms),
      title: "Time from sending the request to receiving the full answer",
    },
    {
      label: "Context",
      value: `${answer.used_context_chunks}`,
      title: "How many retrieved project snippets were fed to the model",
    },
  ];

  return (
    <div className="ask-usage" aria-label="Answer metrics">
      {stats.map((stat) => (
        <div className="ask-usage-stat" key={stat.label} title={stat.title}>
          <span className="ask-usage-k">{stat.label}</span>
          <span className="ask-usage-v">{stat.value}</span>
        </div>
      ))}
      {usage?.estimated ? (
        <span className="ask-usage-note" title="Token counts are estimated for this provider">
          ≈ estimated
        </span>
      ) : null}
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

function Sources({
  workspaceId,
  sources,
  attachedFileNames = [],
  suppressReindexGuidance = false,
}: {
  workspaceId: string;
  sources: RagSource[];
  attachedFileNames?: string[];
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
  const hasAttached = attachedFileNames.length > 0;

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
    <section className={`answer-context${showSources ? " is-open" : ""}`}>
      {hasAttached ? (
        <div className="answer-context-files-row">
          <span className="answer-context-files-label">Attached</span>
          {attachedFileNames.map((name) => (
            <span key={name} className="answer-context-file" title={name}>
              <span className="answer-context-file-icon" aria-hidden="true">▤</span>
              {name}
            </span>
          ))}
        </div>
      ) : null}

      {sources.length > 0 ? (
        <>
          <button
            className="answer-context-bar"
            type="button"
            aria-expanded={showSources}
            onClick={() => setShowSources((current) => !current)}
          >
            <span className="answer-context-bar-dot" aria-hidden="true" />
            <span className="answer-context-bar-text">
              {sources.length} source{sources.length === 1 ? "" : "s"} from your project
            </span>
            <span
              className={`answer-context-caret${showSources ? " is-open" : ""}`}
              aria-hidden="true"
            >
              ⌄
            </span>
          </button>

          {showSources ? (
            <div className="answer-context-detail">
              <p className="answer-context-legend">
                % = how closely it matches your question
              </p>
              {topSourceScoreIsLow ? (
                <p className="answer-context-warn">
                  Top match is weak — the answer may be loosely grounded.
                </p>
              ) : null}
              <div className="answer-context-source-list">
                {visibleSources.map((source, index) => {
                  const isExpanded = expandedSourceIds.has(source.chunk_id);
                  const matchPercent = Math.min(
                    100,
                    Math.max(3, Math.round(source.score * 100)),
                  );
                  return (
                    <article
                      className={`answer-context-source${index === 0 && !showAllSources ? " is-top" : ""}`}
                      key={source.chunk_id}
                    >
                      <div className="answer-context-source-head">
                        <strong title={source.source_path}>
                          {formatSourceLabel(source.source_path)}
                        </strong>
                        <span className="answer-context-score">
                          {formatSourceScore(source.score)}
                        </span>
                      </div>
                      <span className="answer-context-match" aria-hidden="true">
                        <span style={{ width: `${matchPercent}%` }} />
                      </span>
                      <button
                        className="answer-context-preview-toggle"
                        type="button"
                        aria-expanded={isExpanded}
                        onClick={() => toggleSourcePreview(source.chunk_id)}
                      >
                        {isExpanded ? "Hide preview" : "Preview"}
                      </button>
                      {isExpanded ? (
                        <pre className="answer-context-preview">{source.preview}</pre>
                      ) : null}
                    </article>
                  );
                })}
              </div>
              {sources.length > 2 ? (
                <button
                  className="answer-context-more"
                  type="button"
                  onClick={() => setShowAllSources((current) => !current)}
                >
                  {showAllSources
                    ? "Show top matches only"
                    : `Show all ${sources.length} sources (${hiddenSourcesCount} more)`}
                </button>
              ) : null}
            </div>
          ) : null}
        </>
      ) : !hasAttached ? (
        <>
          <EmptyState
            title="No project sources"
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

// One-click "rebuild search context" used by the reindex guidance panel and
// the "answered as general conversation" diagnostic. Runs the same explicit
// jobs API the Models tab uses — nothing happens without this click, which is
// exactly the app's safety contract. Replaces the old copy-these-curl-commands
// panel, which asked non-technical users to operate a terminal.
function RebuildContextButton({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<"idle" | "running" | "done" | "failed">("idle");
  const [progress, setProgress] = useState<string | null>(null);

  async function run() {
    setState("running");
    setProgress(null);
    try {
      const job = await startIndexWorkspaceJob(workspaceId);
      for (;;) {
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        const current = await getWorkspaceJob(workspaceId, job.job_id);
        if (current.status === "succeeded") {
          setState("done");
          setProgress(null);
          return;
        }
        if (current.status === "failed" || current.status === "cancelled") {
          setState("failed");
          setProgress(current.message ?? null);
          return;
        }
        setProgress(current.message ?? null);
      }
    } catch {
      setState("failed");
    }
  }

  if (state === "done") {
    return (
      <span className="rebuild-context-done">
        ✓ Search context rebuilt — ask your question again.
      </span>
    );
  }
  return (
    <span className="rebuild-context-cluster">
      <button
        type="button"
        className="secondary-action rebuild-context-button"
        disabled={state === "running"}
        onClick={() => void run()}
      >
        {state === "running" ? "Rebuilding…" : "Rebuild search context"}
      </button>
      {state === "running" && progress ? (
        <span className="rebuild-context-progress">{progress}</span>
      ) : null}
      {state === "failed" ? (
        <span className="rebuild-context-progress">
          {progress ?? "Could not rebuild — check Models for engine status."}
        </span>
      ) : null}
    </span>
  );
}

function ReindexGuidance({
  workspaceId,
  reason,
}: {
  workspaceId: string;
  reason: string;
}) {
  return (
    <article className="reindex-guidance">
      <div>
        <StatusBadge label="needs rebuild" />
        <strong>Prepare search context</strong>
      </div>
      <p>{reason}</p>
      <RebuildContextButton workspaceId={workspaceId} />
      <small>
        Nothing runs on its own — the rebuild starts only when you press the
        button, and only reads your project files.
      </small>
    </article>
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

// Renders a fenced code block with offline syntax highlighting. If the fence's
// language is one we registered, highlight.js colorizes it; otherwise we show the
// code as safely-escaped plain text (better no colors than wrong colors). The
// HTML highlight.js emits is just <span class="hljs-*"> around escaped text, so
// setting it via dangerouslySetInnerHTML is safe.
function HighlightedCode({ code, language }: { code: string; language?: string }) {
  const html = useMemo(() => {
    const lang = language?.toLowerCase().trim();
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
      } catch {
        // fall through to plain text
      }
    }
    return escapeHtml(code);
  }, [code, language]);

  return <code className="hljs" dangerouslySetInnerHTML={{ __html: html }} />;
}

export function MarkdownAnswer({ content }: { content: string }) {
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
                <HighlightedCode code={block.lines.join("\n")} language={block.language} />
              </pre>
            </div>
          );
        }

        if (block.type === "heading") {
          const level = Math.min(Math.max(block.level ?? 1, 1), 6);
          return (
            <p key={block.id} className="markdown-heading" data-level={level}>
              <InlineMarkdown text={block.lines.join(" ")} />
            </p>
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

        if (block.type === "orderedList") {
          return (
            <ol key={block.id} start={block.start}>
              {block.lines.map((line, index) => (
                <li key={`${block.id}-${index}`}>
                  <InlineMarkdown text={line} />
                </li>
              ))}
            </ol>
          );
        }

        if (block.type === "table" && block.rows && block.rows.length > 0) {
          const [header, ...body] = block.rows;
          const align = block.align ?? [];
          return (
            <div className="markdown-table-wrap" key={block.id}>
              <table className="markdown-table">
                <thead>
                  <tr>
                    {header.map((cell, index) => (
                      <th key={index} style={{ textAlign: align[index] ?? "left" }}>
                        <InlineMarkdown text={cell} />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {body.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, index) => (
                        <td key={index} style={{ textAlign: align[index] ?? "left" }}>
                          <InlineMarkdown text={cell} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
  // Inline code, [links](url), **bold**, *italic* — tokenized purely (see lib/markdown),
  // rendered here as auto-escaped React elements.
  return (
    <>
      {tokenizeInline(text).map((token, index) => {
        switch (token.kind) {
          case "code":
            return <code key={index}>{token.text}</code>;
          case "link":
            return token.href ? (
              <a key={index} href={token.href} target="_blank" rel="noreferrer noopener">
                {token.text}
              </a>
            ) : (
              <span key={index}>{token.text}</span> // unsafe scheme → show text only
            );
          case "bold":
            return <strong key={index}>{token.text}</strong>;
          case "italic":
            return <em key={index}>{token.text}</em>;
          default:
            return <span key={index}>{token.text}</span>;
        }
      })}
    </>
  );
}




function buildSkillContextForOverride(
  overrideId: string,
  skillPreferences: SkillPreferences,
  customSkills: CustomSkill[],
): SkillContextRequest[] {
  const preset = SKILL_PRESETS.find((item) => item.id === overrideId);
  if (preset) {
    const custom = skillPreferences[preset.id]?.customInstructions.trim();
    const instructions = (custom && custom.length > 0
      ? custom
      : preset.defaultInstructions
    ).slice(0, 1200);
    return [{ id: preset.id, name: preset.name, custom_instructions: instructions }];
  }
  const userSkill = customSkills.find((item) => item.id === overrideId);
  if (userSkill) {
    return [
      {
        id: userSkill.id,
        name: userSkill.name,
        custom_instructions: userSkill.instructions.slice(0, 1200),
      },
    ];
  }
  return [];
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
      title="Ask anything about this project"
      message="Type a question below and get an answer grounded in your own files — with the sources it came from. Try “How does deployment work?”, “What are the main risks here?”, or “Where should I start reading?”"
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
      attachedFileNames: [],
      response,
    });
  }
  return items;
}

function createHistoryItem(
  response: WorkspaceQuestionAnswer,
  attachedFileNames: string[] = [],
): AskHistoryItem {
  return {
    id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`,
    question: response.question,
    answer: response.answer,
    llmLabel: `${response.llm_provider}/${response.llm_model ?? "default"}`,
    sourcesCount: response.sources.length,
    warningsCount: response.quality_warnings?.length ?? 0,
    createdAt: new Date().toISOString(),
    attachedFileNames,
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

export function friendlyAskError(message: string): string {
  const normalized = message.trim();
  const lower = normalized.toLowerCase();
  if (lower.includes("load failed")) {
    return "The selected model did not load successfully. This usually means the model is not installed, the local engine is not running, or the model is too heavy for this Mac.";
  }
  if (lower.includes("unable to reach ollama")) {
    return "Ollama is not reachable. Start Ollama or choose a fake/local-ready model for smoke testing.";
  }
  if (lower.includes("selected local model could not answer")) {
    return normalized;
  }
  return normalized || "The request failed.";
}

function isLikelyProjectQuestion(question: string): boolean {
  const words = question.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  return words.some((word) => PROJECT_QUESTION_KEYWORDS.has(word));
}

// Reasoning models (e.g. deepseek-r1, qwq) wrap their thinking in
// <think>…</think> tags inside the answer. Split it out so the UI can show the
// reasoning in a collapsed block and the clean answer below.
function extractReasoning(content: string): { reasoning: string | null; answer: string } {
  if (!content) {
    return { reasoning: null, answer: "" };
  }
  const match = content.match(/<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>/i);
  if (!match) {
    return { reasoning: null, answer: content.trim() };
  }
  const reasoning = match[1].trim();
  const answer = content.replace(match[0], "").trim();
  return { reasoning: reasoning.length > 0 ? reasoning : null, answer };
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
