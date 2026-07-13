import { useState } from "react";

import { getWorkspaceLatestScan } from "../api/client";
import type {
  ProjectCi,
  ProjectCloud,
  ProjectDeploymentFlow,
  ProjectEnvironmentComparison,
  ProjectGraphEntity,
  ProjectGraphFinding,
  ProjectGraphNode,
  ProjectIntelligenceOverviewText,
  ProjectIntelligenceView,
  ProjectReferences,
  RoleBrief,
} from "../api/types";
import { SCANNER_RE } from "./projectIntelligenceShared";

const REFERENCE_KIND_LABELS: Record<string, string> = {
  url: "URLs",
  module_source: "Module sources",
  aws_arn: "AWS ARNs",
  s3_bucket: "S3 buckets",
};

function statusNote(entity: ProjectGraphEntity): string | null {
  if (entity.status === "inferred") return "inferred";
  if (entity.status === "needs_confirmation") return "needs confirming";
  return null;
}

// --- Sections ---

export function SummarySection({
  view,
  overview,
  overviewLoading,
  overviewError,
  onGenerateOverview,
  onInspectFile,
}: {
  view: ProjectIntelligenceView;
  overview: ProjectIntelligenceOverviewText | null;
  overviewLoading: boolean;
  overviewError: string | null;
  onGenerateOverview: () => void;
  onInspectFile?: (path: string) => void;
}) {
  const { summary, important_files, questions } = view;

  return (
    <div className="pi-summary">
      <p className="pi-summary-desc">{summary.description}</p>

      {summary.technology_chips.length > 0 ? (
        <div className="pi-chips">
          {summary.technology_chips.map((chip) => (
            <span key={chip} className="pi-chip">
              {chip}
            </span>
          ))}
        </div>
      ) : null}

      <div className="pi-overview">
        {overview ? (
          <>
            <p className="pi-overview-text">{overview.overview}</p>
            {/* Whose paragraph this is, and what it stands on. The prose is the one
                place in Intelligence a model speaks, so it says so — and names itself,
                because "written by AI" is a claim a reader can only weigh if they know
                which model, working from which analyzers. */}
            <p className="pi-overview-note">
              Written for the {overview.role_label} lens
              {overview.model ? ` by ${overview.model}` : " by the local model"}, from the
              facts on this page
              {overview.grounded_in.length > 0
                ? ` (${overview.grounded_in.join(", ")})`
                : ""}
              . It was given nothing else.
            </p>
          </>
        ) : overviewError ? (
          <p className="pi-muted">{overviewError}</p>
        ) : (
          <button
            type="button"
            className="pi-button"
            onClick={onGenerateOverview}
            disabled={overviewLoading}
          >
            {overviewLoading
              ? "Reading the facts…"
              : `Brief me as a ${view.role_label.toLowerCase()}`}
          </button>
        )}
      </div>

      {important_files.files.length > 0 ? (
        <div className="pi-subblock">
          <p className="pi-eyebrow">Where to start reading</p>
          <p className="pi-hint">The files that explain the most about how this project fits together.</p>
          <ul className="pi-file-list">
            {important_files.files.map((f) => (
              <li key={f.path}>
                {onInspectFile ? (
                  <button type="button" className="pi-file-link" title={`Inspect ${f.path}`} onClick={() => onInspectFile(f.path)}>
                    {f.path}
                  </button>
                ) : (
                  <code>{f.path}</code>
                )}
                {f.reason ? <span className="pi-file-reason">{f.reason}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {questions.questions.length > 0 ? (
        <div className="pi-subblock">
          <p className="pi-eyebrow">Questions for the team</p>
          <p className="pi-hint">Things the files can't answer on their own — worth confirming with a person.</p>
          <ul className="pi-question-list">
            {questions.questions.map((q) => (
              <li key={q.question}>
                <span className="pi-question-text">{q.question}</span>
                <span className="pi-question-reason">{q.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

// Joins a few names for a metric sub-line: "dev, staging, prod" or "a, b +3".
export function InfrastructureSection({ view }: { view: ProjectIntelligenceView }) {
  const { components, images } = view.infrastructure;
  if (components.length === 0 && images.length === 0) {
    return <EmptyNote text="No infrastructure tooling was detected in this project." />;
  }
  return (
    <div className="pi-entity-groups">
      <p className="pi-hint">What provisions and packages this project — each item links back to the file it came from.</p>
      {components.length > 0 ? (
        <EntityList title="Infrastructure tools" entities={components} />
      ) : null}
      {images.length > 0 ? <EntityList title="Container images" entities={images} /> : null}
    </div>
  );
}

export function DeploymentSection({
  view,
  flow,
  ci,
}: {
  view: ProjectIntelligenceView;
  flow?: ProjectDeploymentFlow;
  ci?: ProjectCi;
}) {
  const { pipelines } = view.deployment;
  return (
    <div className="pi-deploy">
      {flow ? <FlowRail flow={flow} /> : null}
      {ci && ci.has_data ? <CiScenarios ci={ci} /> : null}
      {pipelines.length === 0 ? (
        <EmptyNote text="No CI/CD pipelines were detected in this project." />
      ) : (
        <PipelineList pipelines={pipelines} />
      )}
    </div>
  );
}

function FlowRail({ flow }: { flow: ProjectDeploymentFlow }) {
  return (
    <div className="pi-flow">
      <p className="pi-eyebrow">How code reaches an environment</p>
      <p className="pi-hint">Each stage is counted from what was found in the project — follow it left to right.</p>
      <div className="pi-flow-rail">
        {flow.stages.map((stage, i) => (
          <div key={stage.key} className="pi-flow-stage-wrap">
            <div className="pi-flow-stage">
              <span className="pi-flow-count">{stage.count}</span>
              <span className="pi-flow-label">{stage.label}</span>
              <span className="pi-flow-detail">{stage.detail}</span>
            </div>
            {i < flow.stages.length - 1 ? <span className="pi-flow-arrow">→</span> : null}
          </div>
        ))}
      </div>
      {flow.gaps.length > 0 ? (
        <ul className="pi-flow-gaps">
          {flow.gaps.map((gap) => (
            <li key={gap.title}>
              <span className="pi-flow-gap-title">{gap.title}</span>
              <span className="pi-flow-gap-explain">{gap.explanation}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="pi-muted">No gaps detected in the deployment chain.</p>
      )}
    </div>
  );
}

function CiScenarios({ ci }: { ci: ProjectCi }) {
  return (
    <div className="pi-ci">
      <p className="pi-eyebrow">What runs when</p>
      <p className="pi-hint">Which CI workflows fire on each kind of event — inferred from their triggers.</p>
      <div className="pi-ci-list">
        {ci.scenarios.map((s) => (
          <div key={s.key} className="pi-ci-scenario">
            <span className="pi-ci-trigger">{s.label}</span>
            <div className="pi-ci-workflows">
              {s.workflows.map((w) => (
                <span key={w.name} className="pi-ci-workflow" title={w.jobs.join(", ")}>
                  {w.name}
                  {w.jobs.length > 0 ? (
                    <em>{w.jobs.length} job{w.jobs.length === 1 ? "" : "s"}</em>
                  ) : null}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="pi-ci-note">
        Inferred from GitHub Actions triggers — job-level rules may gate some steps further.
      </p>
    </div>
  );
}

// A visual CI/CD flow: for each kind of event, the workflows it fires and the
// jobs inside them, laid out left-to-right (trigger -> workflows -> jobs).
// Security-scan jobs are flagged using the same generic scanner vocabulary the
// Security lens uses. Everything is the deterministic CI data already extracted
// from the project's own workflow files — nothing here is invented.
export function CicdFlowSection({
  ci,
  environments,
  onInspectFile,
}: {
  ci: ProjectCi;
  environments: ProjectGraphEntity[];
  onInspectFile?: (path: string) => void;
}) {
  if (!ci.has_data || ci.scenarios.length === 0) {
    return <EmptyNote text="No CI workflows were detected, so there is no pipeline flow to show." />;
  }
  return (
    <div className="pi-cicd">
      <p className="pi-hint">
        How this project's pipelines flow: each trigger, the workflows it fires, and the jobs inside
        them. Inferred from the workflow files — job-level rules may gate some steps further.
      </p>

      <div className="pi-cicd-flow">
        {ci.scenarios.map((s) => (
          <div key={s.key} className="pi-cicd-lane">
            <div className="pi-cicd-trigger">
              <span className="pi-cicd-trigger-dot" aria-hidden="true" />
              <span className="pi-cicd-trigger-label">{s.label}</span>
            </div>
            <span className="pi-cicd-arrow" aria-hidden="true">→</span>
            <div className="pi-cicd-workflows">
              {s.workflows.map((w) => (
                <div key={`${s.key}-${w.name}`} className="pi-cicd-workflow">
                  <div className="pi-cicd-workflow-head">
                    <span className="pi-cicd-workflow-name">{w.name}</span>
                    {w.source_file ? (
                      onInspectFile ? (
                        <button
                          type="button"
                          className="pi-file-link"
                          title={`Inspect ${w.source_file}`}
                          onClick={() => onInspectFile(w.source_file as string)}
                        >
                          {w.source_file}
                        </button>
                      ) : (
                        <code className="pi-source">{w.source_file}</code>
                      )
                    ) : null}
                  </div>
                  {w.cron && w.cron.length > 0 ? (
                    <span className="pi-cicd-cron">schedule: {w.cron.join(", ")}</span>
                  ) : null}
                  {w.jobs.length > 0 ? (
                    <div className="pi-cicd-jobs">
                      {w.jobs.map((job) => {
                        const isScan = SCANNER_RE.test(job);
                        return (
                          <span
                            key={job}
                            className={`pi-cicd-job${isScan ? " pi-cicd-job-scan" : ""}`}
                            title={isScan ? "Looks like a security/scan step" : undefined}
                          >
                            {job}
                          </span>
                        );
                      })}
                    </div>
                  ) : (
                    <span className="pi-cicd-nojobs">no named jobs detected</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {environments.length > 0 ? (
        <div className="pi-cicd-envs">
          <span className="pi-finding-label">Environments this project defines</span>
          <div className="pi-cicd-env-chips">
            {environments.map((e) => (
              <span key={e.id} className="pi-cicd-env">
                {e.name}
              </span>
            ))}
          </div>
          <p className="pi-ci-note">
            Which workflow deploys to which environment isn't always stated explicitly in the files,
            so this lists the environments rather than wiring each one to a trigger.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function PipelineList({
  pipelines,
}: {
  pipelines: ProjectIntelligenceView["deployment"]["pipelines"];
}) {
  return (
    <div className="pi-pipelines">
      <p className="pi-eyebrow">Pipelines</p>
      <p className="pi-hint">Every CI/CD pipeline found, with the jobs inside it.</p>
      {pipelines.map((p) => (
        <div key={p.id} className="pi-pipeline">
          <div className="pi-pipeline-head">
            <span className="pi-entity-name">{p.name}</span>
            {p.source_file ? <code className="pi-source">{p.source_file}</code> : null}
          </div>
          {p.jobs.length > 0 ? (
            <div className="pi-jobs">
              {p.jobs.map((j) => (
                <span key={j.id} className="pi-job">
                  {j.name}
                  {j.metadata.stage ? <em>{j.metadata.stage}</em> : null}
                </span>
              ))}
            </div>
          ) : (
            <p className="pi-muted">No individual jobs were detected for this pipeline.</p>
          )}
        </div>
      ))}
    </div>
  );
}

export function EnvironmentsSection({
  view,
  comparison,
}: {
  view: ProjectIntelligenceView;
  comparison?: ProjectEnvironmentComparison;
}) {
  const { environments } = view.environments;
  if (environments.length === 0) {
    return (
      <EmptyNote text="No environments were detected from the project's directory structure." />
    );
  }
  const rows = comparison?.environments ?? [];
  const maxEvidence = rows.reduce((m, r) => Math.max(m, r.evidence_count), 0) || 1;
  return (
    <div className="pi-envs">
      <p className="pi-hint">
        Inferred from directory and file naming — confirm them with your team. "Evidence" is
        how many paths point at each environment.
      </p>
      {comparison ? <p className="pi-env-summary">{comparison.summary}</p> : null}

      {rows.length > 0 ? (
        <ul className="pi-env-list pi-env-matrix">
          <li className="pi-env-row pi-env-head" aria-hidden="true">
            <span className="pi-env-name">Environment</span>
            <span className="pi-env-detector">Detected by</span>
            <span className="pi-env-evidence">Evidence</span>
            <span className="pi-env-source">Defined in</span>
          </li>
          {rows.map((row) => {
            const isProd = /(^|[^a-z])(prod|prd)([^a-z]|$)/i.test(row.name);
            return (
              <li key={row.name} className={`pi-env-row${isProd ? " is-prod" : ""}`}>
                <span className="pi-env-name">
                  {row.name}
                  {isProd ? <em>production</em> : null}
                </span>
                <span className="pi-env-detector">{row.analyzer}</span>
                <span className="pi-env-evidence">
                  <span className="pi-env-evidence-bar">
                    <span style={{ width: `${Math.round((row.evidence_count / maxEvidence) * 100)}%` }} />
                  </span>
                  {row.evidence_count} paths
                </span>
                {row.source_file ? (
                  <code className="pi-env-source" title={row.source_file}>{row.source_file}</code>
                ) : (
                  <span className="pi-env-source pi-env-source-empty">—</span>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="pi-chips">
          {environments.map((e) => {
            const note = statusNote(e);
            return (
              <span key={e.id} className="pi-chip pi-chip-env">
                {e.name}
                {note ? <em>{note}</em> : null}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

// A read-only security posture lens: which security checks already run in CI,
// and which deterministic findings are security-relevant. It reads what gates
// exist and where the gaps are — it does not run any scanner itself.
export function SecuritySection({
  scanners,
  findings,
}: {
  scanners: ProjectGraphNode[];
  findings: ProjectGraphFinding[];
}) {
  const high = findings.filter((f) => f.severity === "high").length;
  const summary =
    scanners.length > 0
      ? `${scanners.length} security check${scanners.length === 1 ? "" : "s"} run in CI.`
      : "No automated security checks were detected in CI.";
  const findingLine =
    findings.length > 0
      ? ` ${findings.length} security-relevant finding${findings.length === 1 ? "" : "s"}${high ? ` (${high} high)` : ""} to review.`
      : " Nothing security-relevant flagged by the deterministic analyzers.";

  return (
    <div className="pi-security">
      <p className="pi-hint">{summary}{findingLine}</p>

      <div className="pi-sec-block">
        <p className="pi-eyebrow">Security checks in CI</p>
        {scanners.length > 0 ? (
          <ul className="pi-sec-scanners">
            {scanners.map((s) => (
              <li key={s.id} className="pi-sec-scanner" title={s.source_file ?? undefined}>
                <span className="pi-sec-dot" />
                <span className="pi-sec-scanner-name">{s.name}</span>
                {s.source_file ? <code className="pi-sec-src">{s.source_file}</code> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="pi-muted">
            No scan/audit steps found in the pipelines. Consider adding secret, dependency and IaC scanning.
          </p>
        )}
      </div>

      {findings.length > 0 ? (
        <div className="pi-sec-block">
          <p className="pi-eyebrow">Security-relevant findings</p>
          <ul className="pi-sec-findings">
            {findings.map((f) => (
              <li key={f.id} className="pi-sec-finding">
                <div className="pi-sec-finding-head">
                  <span className={`pi-sev pi-sev-${f.severity}`}>
                    {f.explained?.attention ?? f.severity}
                  </span>
                  <span className="pi-sec-finding-title">{f.title}</span>
                  {f.source_file ? <code className="pi-sec-src">{f.source_file}</code> : null}
                </div>
                {f.explained?.why_it_may_matter ? (
                  <p className="pi-sec-why">{f.explained.why_it_may_matter}</p>
                ) : null}
                {f.explained?.suggested_idea ?? f.recommendation ? (
                  <p className="pi-sec-rec">{f.explained?.suggested_idea ?? f.recommendation}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

// The adaptive role dashboard header: one band that re-frames the same facts for
// whoever is looking. The role label, the facts it leads with, the risks that
// matter to it, and questions worth asking — all decided on the backend from the
// project's own evidence, never hardcoded here.
export function RoleDashboardBrief({
  brief,
  onAskQuestion,
}: {
  brief: RoleBrief;
  onAskQuestion?: (question: string) => void;
}) {
  const hasFacts = brief.facts.length > 0;
  return (
    <section className="pi-brief" aria-label={`${brief.label} dashboard`}>
      <div className="pi-brief-head">
        <span className="pi-brief-eyebrow">{brief.label} dashboard</span>
      </div>
      <p className="pi-brief-focus">{brief.focus}</p>

      {hasFacts ? (
        <div className="pi-brief-facts">
          {brief.facts.map((fact) => (
            <span
              key={fact.label}
              className="pi-brief-fact"
              title={fact.examples.length > 0 ? fact.examples.join(", ") : undefined}
            >
              <span className="pi-brief-fact-count">{fact.count}</span>
              <span className="pi-brief-fact-label">{fact.label}</span>
            </span>
          ))}
        </div>
      ) : null}

      {brief.top_risks.length > 0 ? (
        <p className="pi-brief-risks">
          <span className="pi-finding-label">Worth your attention</span>
          {brief.top_risks.join(" · ")}
        </p>
      ) : null}

      {brief.suggested_questions.length > 0 && onAskQuestion ? (
        <div className="pi-brief-questions">
          <span className="pi-finding-label">Questions worth asking</span>
          <div className="pi-brief-qchips">
            {brief.suggested_questions.map((q) => (
              <button
                key={q}
                type="button"
                className="pi-brief-qchip"
                onClick={() => onAskQuestion(q)}
                title="Open this in Ask"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function RisksSection({
  view,
  onInspectFile,
  onAskQuestion,
}: {
  view: ProjectIntelligenceView;
  onInspectFile?: (path: string) => void;
  onAskQuestion?: (question: string) => void;
}) {
  const { findings } = view.risks;
  if (findings.length === 0) {
    return <EmptyNote text="Nothing looked risky to the deterministic analyzers — no findings to show." />;
  }
  const highlighted = new Set(view.risks.highlighted_categories);
  const high = findings.filter((f) => f.severity === "high").length;
  const medium = findings.filter((f) => f.severity === "medium").length;
  const parts = [`${findings.length} thing${findings.length === 1 ? "" : "s"} to review`];
  if (high > 0) parts.push(`${high} worth a close look`);
  if (medium > 0) parts.push(`${medium} worth reviewing`);
  return (
    <div className="pi-risks">
      <p className="pi-hint">
        {parts.join(" · ")}. These are leads for a human, not verdicts — each one says why it may
        matter and what to check yourself. The ones most relevant to your role are marked and
        listed first.
      </p>
      <ul className="pi-findings">
        {findings.map((f) => (
          <FindingItem
            key={f.id}
            finding={f}
            roleRelevant={highlighted.has(f.category)}
            onInspectFile={onInspectFile}
            onAskQuestion={onAskQuestion}
          />
        ))}
      </ul>
    </div>
  );
}

// --- Small pieces ---

function FindingItem({
  finding,
  roleRelevant = false,
  onInspectFile,
  onAskQuestion,
}: {
  finding: ProjectGraphFinding;
  roleRelevant?: boolean;
  onInspectFile?: (path: string) => void;
  onAskQuestion?: (question: string) => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const hasEvidence = finding.evidence.length > 0 || Boolean(finding.source_file);
  const ex = finding.explained;
  const where = ex?.where ?? finding.source_file;
  return (
    <li className={`pi-finding${roleRelevant ? " is-role-relevant" : ""}`}>
      <div className="pi-finding-head">
        <span className={`pi-severity pi-severity-${finding.severity}`}>
          {ex?.attention ?? finding.severity}
        </span>
        <span className="pi-finding-title">{finding.title}</span>
        {roleRelevant ? <span className="pi-finding-roletag">For your role</span> : null}
      </div>

      <p className="pi-finding-explain">{ex?.what || finding.explanation}</p>

      {/* Every fact is the beginning of a question. Until now the thought ended on the
          dashboard and you had to re-type it in Ask, in your own words, hoping they
          matched the words in the files. The question comes from the fact itself. */}
      {finding.ask && onAskQuestion ? (
        <button
          type="button"
          className="pi-finding-ask"
          onClick={() => onAskQuestion(finding.ask as string)}
          title="Ask this about your project"
        >
          {finding.ask}
        </button>
      ) : null}

      {ex ? (
        <>
          <p className="pi-finding-why">{ex.why_it_may_matter}</p>

          <div className="pi-finding-meta">
            {where ? (
              onInspectFile ? (
                <button
                  type="button"
                  className="pi-file-link"
                  title={`Inspect ${where}`}
                  onClick={() => onInspectFile(where)}
                >
                  {where}
                </button>
              ) : (
                <code className="pi-source">{where}</code>
              )
            ) : null}
            <span className="pi-finding-confidence">{ex.confidence_label}</span>
          </div>

          {ex.check_manually.length > 0 ? (
            <div className="pi-finding-check">
              <span className="pi-finding-label">What to check yourself</span>
              <ul className="pi-finding-checklist">
                {ex.check_manually.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {ex.suggested_idea ? (
            <p className="pi-finding-reco">
              <span className="pi-finding-label">Idea to consider</span>
              {ex.suggested_idea}
              <span className="pi-finding-reco-note"> — review, don’t auto-apply.</span>
            </p>
          ) : null}
        </>
      ) : (
        finding.recommendation && <p className="pi-finding-reco">{finding.recommendation}</p>
      )}

      {hasEvidence ? (
        <>
          <button
            type="button"
            className="pi-link"
            onClick={() => setShowEvidence((v) => !v)}
          >
            {showEvidence ? "Hide sources" : "Show sources"}
          </button>
          {showEvidence ? (
            <div className="pi-evidence">
              {finding.source_file ? (
                <code className="pi-source">{finding.source_file}</code>
              ) : null}
              {finding.evidence.map((ev, i) => (
                <span key={i} className="pi-evidence-line">
                  {ev}
                </span>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </li>
  );
}

function infraMetaChips(e: ProjectGraphEntity): string[] {
  const chips: string[] = [];
  const m = e.metadata || {};
  if (m.files) chips.push(`${m.files} files`);
  if (m.providers) chips.push(m.providers);
  // Only the positive signal is reliable: a Terraform stack managed by Terragrunt
  // keeps its backend in terragrunt.hcl, so "no backend block in .tf" is not the
  // same as "no remote state" — don't assert the negative.
  if (m.remote_state === "True") {
    chips.push(m.remote_state_via ? `remote state · ${m.remote_state_via}` : "remote state");
  }
  if (m.modules === "True") chips.push("modules");
  if (m.charts) chips.push(`${m.charts} chart(s)`);
  if (m.workloads) chips.push(`${m.workloads} workload(s)`);
  if (m.namespaces) chips.push(m.namespaces);
  return chips;
}

function EntityList({ title, entities }: { title: string; entities: ProjectGraphEntity[] }) {
  return (
    <div className="pi-entity-group">
      <p className="pi-eyebrow">{title}</p>
      <ul className="pi-entity-list">
        {entities.map((e) => {
          const note = statusNote(e);
          const chips = infraMetaChips(e);
          return (
            <li key={e.id} className="pi-entity pi-entity-block">
              <div className="pi-entity-row">
                <span className="pi-entity-name">{e.name}</span>
                {note ? <span className="pi-entity-note">{note}</span> : null}
                {e.source_file ? <code className="pi-source">{e.source_file}</code> : null}
              </div>
              {chips.length > 0 ? (
                <div className="pi-entity-meta">
                  {chips.map((c) => (
                    <span key={c} className="pi-meta-chip">
                      {c}
                    </span>
                  ))}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function CloudSection({ cloud }: { cloud: ProjectCloud }) {
  if (cloud.providers.length === 0) {
    return <EmptyNote text="No managed cloud services were detected in the infrastructure." />;
  }
  return (
    <div className="pi-cloud">
      <p className="pi-hint">
        Managed cloud services provisioned by the project's infrastructure-as-code. The number is
        how many resources of that service were found; the bar shows its relative footprint.
      </p>
      {cloud.providers.map((provider) => {
        const max = provider.services.reduce((m, s) => Math.max(m, s.resources), 0) || 1;
        const top = provider.services.slice(0, 3).map((s) => s.service).join(", ");
        return (
          <section key={provider.provider} className="pi-cloud-provider">
            <div className="pi-cloud-provider-head">
              <span className="pi-cloud-provider-name">{provider.provider}</span>
              <span className="pi-cloud-provider-count">{provider.service_count} services</span>
              {top ? <span className="pi-cloud-top">most used: {top}</span> : null}
            </div>
            <div className="pi-cloud-services">
              {provider.services.map((s) => (
                <div key={s.service} className="pi-cloud-service" title={s.source_file ?? ""}>
                  <div className="pi-cloud-service-row">
                    <span className="pi-cloud-service-name">{s.service}</span>
                    <span className="pi-cloud-service-count">{s.resources}</span>
                  </div>
                  <span className="pi-cloud-bar">
                    <span style={{ width: `${Math.round((s.resources / max) * 100)}%` }} />
                  </span>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

export function ReferencesSection({ references }: { references: ProjectReferences }) {
  if (references.groups.length === 0) {
    return <EmptyNote text="No external references were found in the project's files." />;
  }
  return (
    <div className="pi-refs">
      <p className="pi-hint">
        External things the project points at — ARNs, URLs and module sources pulled from its
        files. The number is how many times each appears.
      </p>
      {references.groups.map((group) => (
        <ReferenceGroup key={group.kind} group={group} />
      ))}
    </div>
  );
}

function ReferenceGroup({
  group,
}: {
  group: ProjectReferences["groups"][number];
}) {
  const [showAll, setShowAll] = useState(false);
  const LIMIT = 12;
  const items = showAll ? group.items : group.items.slice(0, LIMIT);
  return (
    <section className="pi-ref-group">
      <div className="pi-ga-head">
        <span className="pi-eyebrow">{REFERENCE_KIND_LABELS[group.kind] ?? group.kind}</span>
        <span className="pi-ga-hint">{group.items.length}</span>
      </div>
      <ul className="pi-ref-list">
        {items.map((item) => (
          <li
            key={item.value}
            className="pi-ref-item"
            title={`${item.value}${item.source_file ? ` — ${item.source_file}` : ""}`}
          >
            <code className="pi-ref-value">{item.value}</code>
            {item.count > 1 ? <span className="pi-ref-count">×{item.count}</span> : null}
          </li>
        ))}
      </ul>
      {group.items.length > LIMIT ? (
        <button type="button" className="pi-link" onClick={() => setShowAll((v) => !v)}>
          {showAll ? "Show fewer" : `Show all ${group.items.length}`}
        </button>
      ) : null}
    </section>
  );
}

function EmptyNote({ text }: { text: string }) {
  return <p className="pi-muted pi-empty-note">{text}</p>;
}

// Compares the snapshot's "files:N" signature to the current scan's file count.
// Returns true when they differ (the map is out of date). Best-effort only.
export async function checkStale(
  workspaceId: string,
  scanSignature: string | null,
  signal: AbortSignal,
): Promise<boolean> {
  if (!scanSignature || !scanSignature.startsWith("files:")) return false;
  const builtCount = Number.parseInt(scanSignature.slice("files:".length), 10);
  if (Number.isNaN(builtCount)) return false;
  try {
    const scan = await getWorkspaceLatestScan(workspaceId, { signal });
    if (!scan || !Array.isArray(scan.files)) return false;
    return scan.files.length !== builtCount;
  } catch {
    return false;
  }
}

/** A folder of documentation, as itself.
 *
 * Pointed at an exported wiki, this app used to answer with a list of things it had
 * not found — no infrastructure, no environments, no pipelines. Every line true, and
 * the screen as a whole a lie: a wiki is not a broken repository. These are the facts
 * it does carry: the areas its own titles announce, the decisions it records, and the
 * pages themselves — with the two numbers that matter for a page, how many others
 * point at it and whether it still has attachments to look at.
 */
export function DocumentsSection({
  view,
  onInspectFile,
}: {
  view: ProjectIntelligenceView;
  onInspectFile?: (path: string) => void;
}) {
  const documents = view.documents;
  if (!documents) return null;

  const pages = [...documents.pages, ...documents.decisions];
  // Only a knowledge base has a link graph. In a repository the backend does not send
  // one — a hundred READMEs do not point at each other and were never meant to — and a
  // column of "nothing links to it" under them would be the mirror of telling a wiki it
  // has no tests. Where there is no graph, the documents are simply listed, by path.
  const linked = pages.some((page) => page.metadata?.linked_from !== undefined);
  if (linked) {
    pages.sort(
      (a, b) => Number(b.metadata?.linked_from ?? 0) - Number(a.metadata?.linked_from ?? 0),
    );
  } else {
    pages.sort((a, b) => (a.source_file ?? a.name).localeCompare(b.source_file ?? b.name));
  }

  return (
    <div className="pi-stack">
      {documents.topics.length > 0 ? (
        <div className="pi-block">
          <h4 className="pi-block-title">Areas</h4>
          <p className="pi-hint">
            Taken from the pages' own titles — a wiki's naming convention is the closest thing
            it has to a schema.
          </p>
          <div className="pi-chips">
            {documents.topics.map((topic) => (
              <span className="pi-chip" key={topic.id}>
                {topic.name} · {topic.metadata?.pages ?? "0"}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {documents.decisions.length > 0 ? (
        <div className="pi-block">
          <h4 className="pi-block-title">Decisions</h4>
          <ul className="pi-list">
            {documents.decisions.map((decision) => (
              <li key={decision.id}>
                <button
                  type="button"
                  className="pi-file-link"
                  onClick={() => decision.source_file && onInspectFile?.(decision.source_file)}
                >
                  {decision.name}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="pi-block">
        {/* A repository has documents, not pages — the list learned that; the heading
            above it had not. */}
        <h4 className="pi-block-title">
          {linked ? "Pages" : "Documents"} ({pages.length})
        </h4>
        <ul className="pi-list pi-page-list">
          {pages.slice(0, 60).map((page) => {
            const linkedFrom = Number(page.metadata?.linked_from ?? 0);
            const attachments = Number(page.metadata?.attachments ?? 0);
            return (
              <li className="pi-page-row" key={page.id}>
                <button
                  type="button"
                  className="pi-file-link"
                  onClick={() => page.source_file && onInspectFile?.(page.source_file)}
                >
                  {page.name}
                </button>
                {/* On its own line, quiet: the title is what the eye is scanning for, and
                    "nothing links to it" running into the name read like part of it. */}
                <span className="pi-muted pi-page-meta">
                  {linked
                    ? linkedFrom > 0
                      ? `linked from ${linkedFrom} page${linkedFrom === 1 ? "" : "s"}`
                      : "nothing links to it"
                    : (page.source_file ?? "")}
                  {attachments > 0
                    ? ` · ${attachments} attachment${attachments === 1 ? "" : "s"}`
                    : ""}
                </span>
              </li>
            );
          })}
        </ul>
        {pages.length > 60 ? (
          <p className="pi-hint">
            Showing 60 of {pages.length} — Ask searches all of them.
          </p>
        ) : null}
      </div>
    </div>
  );
}

/** The sections a project earns by having the things in them.
 *
 * Code, tests, data, API: four kinds of fact, one renderer, because they differ only
 * in which lists they carry. A project shows the ones it has — a library has modules
 * and no schema, a wiki has neither — and the role decides which comes first. The old
 * screen showed all of them to everyone and wrote "not detected" under most, which is
 * how a perfectly healthy project came to look broken.
 */
const FACT_GROUPS: Record<string, { key: string; label: string }[]> = {
  code: [
    { key: "applications", label: "Applications" },
    { key: "modules", label: "Modules" },
    { key: "dependencies", label: "Dependencies" },
  ],
  tests: [{ key: "suites", label: "Test suites" }],
  data: [
    { key: "tables", label: "Tables" },
    { key: "migrations", label: "Migrations, in the order they apply" },
  ],
  api: [
    { key: "endpoints", label: "Endpoints" },
    { key: "domain_entities", label: "Things the system speaks in" },
  ],
};

export function FactsSection({
  view,
  section,
  onInspectFile,
}: {
  view: ProjectIntelligenceView;
  section: string;
  onInspectFile?: (path: string) => void;
}) {
  const payload = (view as unknown as Record<string, Record<string, ProjectGraphEntity[]>>)[
    section
  ];
  const groups = FACT_GROUPS[section];
  if (!payload || !groups) return null;

  return (
    <div className="pi-stack">
      {groups.map(({ key, label }) => {
        const items = payload[key] ?? [];
        if (items.length === 0) return null;
        return (
          <div className="pi-block" key={key}>
            <h4 className="pi-block-title">
              {label} ({items.length})
            </h4>
            <ul className="pi-list">
              {items.slice(0, 100).map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="pi-file-link"
                    onClick={() => item.source_file && onInspectFile?.(item.source_file)}
                  >
                    {item.name}
                  </button>
                  {item.metadata?.run_with ? (
                    <span className="pi-muted"> · run with {item.metadata.run_with}</span>
                  ) : null}
                  {item.metadata?.test_cases ? (
                    <span className="pi-muted"> · {item.metadata.test_cases} cases</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
