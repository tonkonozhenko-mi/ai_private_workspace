# Project intelligence & read-only analysis

> The full detail behind the short overview in the [README](../README.md#project-intelligence-and-read-only-analysis). Everything here is **read-only by construction** — it reads and explains your project; it never writes files, runs commands, or changes anything on your computer.

Beyond search, the app builds a **map of your project** and gives you two local
analysis tools that work over it. The guiding principle is the same throughout:
every statement is backed by something found in your own files, the facts are
produced deterministically wherever possible, and the analysis is **read-only by
construction** — it looks and explains, but it never writes files, runs commands,
or changes anything on your computer.

### Project Intelligence — the map

On an explicit action, the app assembles a **role-neutral evidence graph** from
deterministic analyzers (Terraform, Terragrunt, GitLab CI, GitHub Actions,
Kubernetes, Helm, and Python). The result is a set of honest, source-linked views:
a summary, infrastructure, deployment flow, environments, risks, a **Cloud** tab
listing the AWS / Google Cloud / Azure services your IaC provisions, a
**References** tab (URLs, module sources, ARNs), and an interactive **Map**.

A **role lens** (Developer, DevOps, Tester, Business analyst) turns the same facts
into an **adaptive dashboard** for who's looking — a role-framed brief that leads
with the facts that matter to that role (environments, pipelines, modules…), the
risks worth its attention, and a row of suggested questions you can click straight
into Ask. It re-orders and re-frames; it never changes the facts. Inferred facts
(for example, an environment guessed from a directory name) are always labelled as
inferred. The only LLM-written pieces — a plain-language overview and the "ask the
graph" answer — are constrained strictly to the graph's facts.

### CI/CD flow

A visual **CI/CD flow** lays out the pipelines as they actually fire: each trigger
(push to a feature branch, push to the default branch, pull request, tag/release,
schedule, manual) flows into the workflows it runs and the jobs inside them, with
schedules and the workflow file one click from the inspector. Security/scan jobs
are flagged, and the environments the project defines are listed alongside.
Everything is read straight from the project's own workflow files.

### Project activity & change coupling — read from git

A read-only pass over the repository's **own git history** (no model) becomes a
readable briefing: how active the project is, who knows which parts of the code
(the right people to ask), how it ships (branch strategy, long-lived branches,
merge flow), and the files where work concentrates. It also surfaces **change
coupling** — pairs of files that keep changing together in the same commits;
cross-module pairs are flagged as a likely hidden dependency the import graph
misses. Like the map, the card re-frames itself for the role you chose.

### File inspector

Open any file — from search, the "where to start" lists, or the hotspots — for a
read-only lens on it: its owner and recent changes (from git), what it changes
together with, what it connects to in the project map (its blast radius — what it
depends on and what it affects), and which risks touch it. All composed from data
the app already computed.

### Security review

A read-only **Security review** reports what security gates already exist and where
the gaps are: which scan/audit steps run in CI (secret, dependency, and IaC
scanning) and which deterministic findings are security-relevant — permissions,
secrets, public exposure, encryption, IAM/access — each with a recommendation and
the file it came from. It reports on scanners; it never runs one.

Every finding — here and in the **Risks** tab — reads as a lead for a human, not a
verdict: what was found, **why it may matter**, where (one click to the inspector),
how confident we are in plain language, and **what to check yourself**, with the
recommendation framed as an idea to review rather than a fix to auto-apply. The
language is deliberately "needs review", to inform rather than alarm.

### Project groups — several repositories as one project

A **group** treats a set of repositories as a single project. Ask once and the
answer is drawn from every member (each source labelled with the repo it came
from); a portfolio Home rolls up each repo's activity; and group Intelligence
**compares rather than merges** — environments in a repo×environment matrix,
technologies split into common / shared / unique, and risks grouped by pattern
with a per-repo breakdown. Create a group by dragging one project onto another;
member repositories stay independent workspaces underneath.

### Memory — about the project, and about you

The app learns over time, in two local, fully-editable layers. **Project memory**
keeps durable notes, decisions and corrections about a project ("prod is called
'prd' here"), fed back into every answer for that workspace. **Your profile**
(Settings → About you) holds stable facts about *you* — your role, the language
to answer in, how concise you like answers, your team's conventions — applied to
**every** project, in Ask and the Investigator, so you don't re-explain yourself.

Both are honest about how they work: selection for a prompt is pinned + keyword +
recency, never an LLM guess, and everything is visible, editable and deletable.
The profile can also **suggest** facts from a conversation, but **review-first** —
the local model proposes candidates and nothing is saved until you keep it.
Nothing about you ever leaves the machine.

### The Watcher — deterministic change tracking

The Watcher answers **"what changed since I last looked?"** On demand it
re-scans the project, rebuilds the graph, and **diffs it against the previous
snapshot** — reporting new environments, newly detected technologies, new and
resolved risks, new cloud services, and more. The facts come entirely from
comparing two graphs (no model needed); the digest is persisted so it survives
restarts. It is the foundation for scheduled, hands-off drift detection.

### The Investigator — read-only, evidence-backed analysis

The Investigator answers harder, multi-step questions — _"How does a request
reach the database?"_, _"Who should I ask about this module?"_ — by running a
small **ReAct loop**: at each step the local model picks **one read-only tool**,
reads the result, and decides what to do next, until it can answer.

There is deliberately **one** investigator, not a swarm of narrow tools. Adding a
new capability means giving it another read-only tool, which widens what it can
reason about — the investigator decides which tools to combine for a given
question. Its toolbox is intentionally small and safe:

| Tool | What it does |
| --- | --- |
| `search_code` | semantic search over the indexed code and docs |
| `read_file` | read a project file's contents |
| `graph_query` | look up entities and relations in the project map |
| `list_files` | list project files matching a substring |
| `git_history` | who changed a file, and its recent commits |
| `ci_triggers` | what CI runs on push / pull request / tag / schedule |

The loop is built for **local models**: the protocol is plain text the app parses
itself (`ACTION: <tool>: <input>` … `FINAL: <answer>`), with validation, a couple
of retries on malformed replies, a step budget, and a graceful "out of steps"
fallback rather than a guess. Every answer comes with a **transparent trace**
(each tool call, its input, and what it returned) and the **sources consulted**,
collected deterministically — so the answer is always backed by real evidence,
even if the model forgets to cite.

**What it can reason about**

Through those tools the Investigator draws on the indexed code and docs, the
project map (infrastructure, services, environments, pipelines, cloud services,
risks), individual files, the git history and file ownership, and CI trigger
behaviour. It is strongest on understanding-and-orientation questions, not on
predicting runtime behaviour it can't see in the files.

**Questions it answers well**

- _Architecture & code_ — "How does a request reach the database?", "Which
  modules depend on the billing module?", "Where is authentication handled?"
- _Infrastructure & deployment_ — "What gets deployed to production?", "Which AWS
  services does this project use?", "What runs in CI when I push to a feature
  branch versus open a pull request?"
- _Ownership & history_ — "Who should I ask about the payments module?", "When did
  this config last change, and why?"
- _Risk & orientation_ — "What are the biggest risks flagged here?", "Where should
  I start reading to understand this repo?"

When the answer isn't in the project's files, it says so plainly rather than
guessing.

**How the analysis stays trustworthy**

- **Read-only by construction** — no analysis tool writes a file or runs a command.
- **Local and private** — everything runs on your machine; your code never leaves it.
- **Evidence-backed** — deterministic facts first; sources attached to every answer.
- **Transparent** — the Investigator shows exactly which tools it used and why.
- **Bounded** — a step budget keeps a run finite; you stay in control.
