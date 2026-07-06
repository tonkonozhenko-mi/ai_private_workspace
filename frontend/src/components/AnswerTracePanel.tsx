import { useEffect, useRef, useState } from "react";

import { investigateProject } from "../api/client";
import type { InvestigationResponse, RagQualityWarning } from "../api/types";
import { formatSourceLabel } from "../lib/sourceLabel";

export interface TraceFile {
  source_path: string;
  repo?: string | null;
  // Optional per-chunk info so several chunks of the same file are distinguishable
  // (otherwise "AGENTS.md" ×4 looks like a duplicate bug). chunk_id often encodes
  // a trailing line number; score is the retrieval relevance for that chunk.
  chunk_id?: string | null;
  score?: number | null;
}

// A short, honest differentiator for a chunk of a file: the line number if the
// chunk_id encodes one (…:path:14), else the retrieval score as a percentage.
function chunkDetail(file: TraceFile): string | null {
  const id = file.chunk_id ?? "";
  const lineMatch = /:(\d+)$/.exec(id);
  if (lineMatch) return `line ${lineMatch[1]}`;
  if (typeof file.score === "number" && Number.isFinite(file.score)) {
    return `${Math.round(Math.max(0, Math.min(1, file.score)) * 100)}% match`;
  }
  return null;
}

export interface TraceMemory {
  kind: string;
  text: string;
  grounding?: string | null;
}

export interface AnswerTracePanelProps {
  memoryUsed: number;
  factsUsed: number;
  chunks: number;
  files: TraceFile[];
  guardrails?: string[];
  memoryDetails?: TraceMemory[];
  warnings?: RagQualityWarning[];
  latencyMs?: number | null;
  scope?: "project" | "group";
  // When present, the panel offers an opt-in "Investigate deeper" that runs the
  // real agent and replaces the derived steps with its true ReAct transcript.
  investigate?: { workspaceId: string; question: string; role?: string | null };
  onClose: () => void;
}

function labelize(value: string): string {
  return value.replaceAll("_", " ");
}

function plural(n: number): string {
  return n === 1 ? "" : "s";
}

export function AnswerTracePanel({
  memoryUsed,
  factsUsed,
  chunks,
  files,
  guardrails = [],
  memoryDetails = [],
  warnings = [],
  latencyMs = null,
  scope = "project",
  investigate,
  onClose,
}: AnswerTracePanelProps) {
  const [tab, setTab] = useState<"reasoning" | "sources">("reasoning");
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [investigating, setInvestigating] = useState(false);
  const [investError, setInvestError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const memoryWord = scope === "group" ? "memory across repos" : "project memory";
  const fileWord = scope === "group" ? "file" : "source file";

  // Grounding-related warnings are the honest confidence signal — no invented %.
  const grounding = warnings.filter(
    (w) =>
      /ground|hallucin|verify|unsupported|abstain/i.test(w.code) ||
      /ground|verify|not found|couldn't find/i.test(w.message),
  );

  const derivedSteps: { icon: string; title: string; detail: string; muted?: boolean }[] = [
    {
      icon: "🧠",
      title: "Understood your question",
      detail: "Parsed what you're asking about this project.",
    },
    memoryUsed > 0
      ? { icon: "💾", title: `Searched ${memoryWord}`, detail: `${memoryUsed} note${plural(memoryUsed)} used` }
      : { icon: "💾", title: `Searched ${memoryWord}`, detail: "no notes matched", muted: true },
    files.length > 0
      ? {
          icon: "📄",
          title: "Retrieved source files",
          detail: `${files.length} ${fileWord}${plural(files.length)} · ${chunks} chunk${plural(chunks)}`,
        }
      : { icon: "📄", title: "Retrieved source files", detail: "nothing confident found", muted: true },
  ];
  if (factsUsed > 0) {
    derivedSteps.push({
      icon: "🕸",
      title: "Used the project map",
      detail: `${factsUsed} fact${plural(factsUsed)} informed the answer`,
    });
  }
  if (guardrails.length > 0) {
    derivedSteps.push({
      icon: "🛡",
      title: "Applied guardrails",
      detail: `${guardrails.length} rule${plural(guardrails.length)} enforced`,
    });
  }
  derivedSteps.push(
    grounding.length > 0
      ? {
          icon: "⚠",
          title: "Grounding check",
          detail: `${grounding.length} thing${plural(grounding.length)} to verify`,
          muted: true,
        }
      : { icon: "✓", title: "Grounding check passed", detail: "no terms stated outside the sources" },
  );

  const runInvestigation = async () => {
    if (!investigate || investigating) return;
    setInvestError(null);
    setInvestigating(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const result = await investigateProject(
        investigate.workspaceId,
        investigate.question,
        investigate.role ?? undefined,
        { signal: controller.signal },
      );
      setInvestigation(result);
    } catch (error) {
      if ((error as Error)?.name !== "AbortError") {
        setInvestError("Couldn't run the deeper investigation. Try again.");
      }
    } finally {
      setInvestigating(false);
    }
  };

  const byRepo = files.some((f) => f.repo);

  // Collapse exact-duplicate rows (same chunk), but keep distinct chunks of one
  // file as separate rows — differentiated by line/score below.
  const seenFileKeys = new Set<string>();
  const uniqueFiles = files.filter((f) => {
    const key = f.chunk_id ?? `${f.repo ?? ""}:${f.source_path}`;
    if (seenFileKeys.has(key)) return false;
    seenFileKeys.add(key);
    return true;
  });

  return (
    <>
      <div className="trace-backdrop" onClick={onClose} aria-hidden="true" />
      <aside className="trace-panel" role="dialog" aria-label="How the answer was built">
        <header className="trace-head">
          <div>
            <h3>How the AI reached this</h3>
            <p>The reasoning and the exact sources behind this answer.</p>
          </div>
          <button className="trace-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>
        <div className="trace-tabs" role="tablist">
          <button
            className={`trace-tab ${tab === "reasoning" ? "on" : ""}`}
            onClick={() => setTab("reasoning")}
            role="tab"
            aria-selected={tab === "reasoning"}
          >
            Reasoning
          </button>
          <button
            className={`trace-tab ${tab === "sources" ? "on" : ""}`}
            onClick={() => setTab("sources")}
            role="tab"
            aria-selected={tab === "sources"}
          >
            Sources
          </button>
        </div>
        <div className="trace-body">
          {tab === "reasoning" ? (
            investigation ? (
              (() => {
                // The deeper pass only "refines" when it actually converged.
                // When it ran out of budget or couldn't answer, saying it "may
                // refine the answer" is misleading — mark it tentative instead so
                // a decent quick answer isn't undermined by an inconclusive agent.
                const inconclusive = investigation.stopped_reason !== "answered";
                return (
                  <div className="trace-react">
                    <p className={`trace-react-lead ${inconclusive ? "inconclusive" : ""}`}>
                      Real agent run · {investigation.used_steps} step
                      {plural(investigation.used_steps)} · stopped:{" "}
                      {labelize(investigation.stopped_reason)}
                    </p>
                    {investigation.steps.map((step, index) => {
                      const isFormat = step.tool === "(format)";
                      return (
                        <div
                          className={`trace-react-step ${isFormat ? "muted" : ""}`}
                          key={index}
                        >
                          <span className="trace-react-n">{index + 1}</span>
                          <div>
                            {step.thought ? <p className="thought">{step.thought}</p> : null}
                            <p className="tool">
                              <span className="k">
                                {isFormat ? "format retry" : labelize(step.tool)}
                              </span>
                              {step.tool_input ? (
                                <span className="in"> · {step.tool_input}</span>
                              ) : null}
                            </p>
                            {step.observation ? <p className="obs">{step.observation}</p> : null}
                          </div>
                        </div>
                      );
                    })}
                    {investigation.answer ? (
                      <div
                        className={`trace-src ${inconclusive ? "warn" : ""}`}
                        style={{ marginTop: "12px" }}
                      >
                        <div className="t">
                          <strong>
                            {inconclusive ? "Agent conclusion (tentative):" : "Agent conclusion:"}
                          </strong>{" "}
                          {investigation.answer}
                        </div>
                      </div>
                    ) : null}
                    <p className="trace-foot">
                      {inconclusive
                        ? "This deeper pass didn't converge — treat its take as tentative; the quick answer above is usually more reliable."
                        : "A fresh, deeper pass — its take may refine the answer above."}
                    </p>
                  </div>
                );
              })()
            ) : (
              <>
                <ol className="trace-steps">
                  {derivedSteps.map((step, index) => (
                    <li key={index} className={`trace-step ${step.muted ? "muted" : "done"}`}>
                      <span className="trace-mk" aria-hidden="true">
                        {step.icon}
                      </span>
                      <span className="trace-step-text">
                        <span className="tt">{step.title}</span>
                        <span className="ss">{step.detail}</span>
                      </span>
                    </li>
                  ))}
                </ol>
                {latencyMs != null ? (
                  <p className="trace-foot">Answered locally in {(latencyMs / 1000).toFixed(1)}s.</p>
                ) : null}
                {investigate ? (
                  <div className="trace-invite">
                    <button className="trace-invite-btn" onClick={runInvestigation} disabled={investigating}>
                      {investigating ? (
                        <>
                          <span className="trace-spin" aria-hidden="true" /> Investigating…
                        </>
                      ) : (
                        <>🔍 Investigate deeper — show the agent's real steps</>
                      )}
                    </button>
                    <p className="trace-invite-note">
                      Runs the agent live and replaces the summary above with its true step-by-step trace.
                    </p>
                    {investError ? <p className="trace-invite-err">{investError}</p> : null}
                  </div>
                ) : null}
              </>
            )
          ) : (
            <div className="trace-sources">
              {memoryDetails.length > 0 ? (
                <section className="trace-grp">
                  <h4>
                    <span className="dot mem" aria-hidden="true" /> Memory ({memoryDetails.length})
                  </h4>
                  {memoryDetails.map((memory, index) => (
                    <div className="trace-src" key={index}>
                      <div className="t">{memory.text}</div>
                      <div className="m">
                        <span className="kind">{labelize(memory.kind)}</span>
                        {memory.grounding ? <span>· {memory.grounding}</span> : null}
                      </div>
                    </div>
                  ))}
                </section>
              ) : memoryUsed > 0 ? (
                <section className="trace-grp">
                  <h4>
                    <span className="dot mem" aria-hidden="true" /> Memory
                  </h4>
                  <div className="trace-src">
                    <div className="t">
                      {memoryUsed} memory note{plural(memoryUsed)} from across the group informed this answer.
                    </div>
                  </div>
                </section>
              ) : null}
              {uniqueFiles.length > 0 ? (
                <section className="trace-grp">
                  <h4>
                    <span className="dot file" aria-hidden="true" /> Files ({uniqueFiles.length})
                  </h4>
                  {uniqueFiles.map((file, index) => {
                    const detail = chunkDetail(file);
                    return (
                      <div className="trace-src file" key={file.chunk_id ?? index}>
                        <div className="t">
                          {byRepo && file.repo ? <span className="repo">{file.repo}/</span> : null}
                          {formatSourceLabel(file.source_path)}
                          {detail ? <span className="chunk-detail"> · {detail}</span> : null}
                        </div>
                      </div>
                    );
                  })}
                </section>
              ) : null}
              {factsUsed > 0 ? (
                <section className="trace-grp">
                  <h4>
                    <span className="dot map" aria-hidden="true" /> Project map
                  </h4>
                  <div className="trace-src">
                    <div className="t">
                      {factsUsed} fact{plural(factsUsed)} from the dependency graph informed this answer.
                    </div>
                  </div>
                </section>
              ) : null}
              {guardrails.length > 0 ? (
                <section className="trace-grp">
                  <h4>
                    <span className="dot grd" aria-hidden="true" /> Guardrails ({guardrails.length})
                  </h4>
                  {guardrails.map((rule, index) => (
                    <div className="trace-src" key={index}>
                      <div className="t">🛡 {rule}</div>
                    </div>
                  ))}
                </section>
              ) : null}
              {scope === "project" ? (
                <section className="trace-grp">
                  <h4>
                    <span className="dot ok" aria-hidden="true" /> Grounding
                  </h4>
                  {grounding.length > 0 ? (
                    grounding.map((warning, index) => (
                      <div className="trace-src warn" key={index}>
                        <div className="t">{warning.message}</div>
                        {warning.evidence.length > 0 ? (
                          <div className="m">{warning.evidence.join(", ")}</div>
                        ) : null}
                      </div>
                    ))
                  ) : (
                    <div className="trace-src">
                      <div className="t">
                        ✓ Answer stays within the provided sources — nothing stated as fact that isn't in
                        the retrieved text.
                      </div>
                    </div>
                  )}
                </section>
              ) : null}
              <p className="trace-foot">Shown from what actually went into the prompt.</p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
