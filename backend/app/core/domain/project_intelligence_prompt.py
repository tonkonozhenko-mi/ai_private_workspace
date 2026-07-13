"""What the local model is told, and why.

Two jobs live here: a free-text question over the map, and the short prose overview
at the top of Intelligence. Both stand on the same footing — the LLM *explains*
facts the deterministic analyzers already established, and may not invent services,
pages, environments, technologies or risks.

Until now the facts were serialized the same way for every project and every role: a
fixed block of infrastructure, pipelines, environments and counts. Point the app at a
folder of documentation and that block was six lines of "none detected", so the model
did the only thing it could with them — it wrote a paragraph about absences ("no
services, no CI/CD; the deployment methodology remains unclear"). Every word true;
the paragraph worthless.

So the prompt is now assembled from the project in front of it:

* **The facts follow the project.** Only the sections the project actually HAS are
  serialized, in the order the role's lens puts them. A wiki's facts are its areas,
  its decisions and its stale pages; a repository's are its modules and pipelines.
  Nothing is described by what it lacks.
* **The questions follow the role.** A tester and a DBA looking at one project need
  different paragraphs, and "briefing a Tester" alone never produced one. Each role
  brings the two or three questions its own working day starts with.
* **A documentation folder is not the system it documents.** The pages of a wiki
  describe someone's AWS estate; the folder contains no AWS. Saying "this project
  uses S3" would be a lie assembled out of true sentences, so the model is told,
  explicitly, whose facts it is holding.
"""

from app.core.domain.role_lens import Section

# What each role's day starts with. Not decoration: this is the difference between a
# paragraph written *for* a person and a paragraph written *near* them. Kept to two or
# three questions, because a model given ten answers none of them.
_ROLE_QUESTIONS: dict[str, list[str]] = {
    "developer": [
        "what this codebase is and where its entry points are",
        "which parts are most likely to surprise someone changing them",
    ],
    "devops": [
        "how this is built, deployed and run",
        "what is most likely to break a deploy, and what is not visible in the files",
    ],
    "tester": [
        "what can be tested here today, and how those tests are run",
        "which behaviour is covered by nothing, and where a regression would hide",
    ],
    "business_analyst": [
        "what this system does in business terms, and what nouns it speaks in",
        "which behaviour is decided in code rather than documented",
    ],
    "manager": [
        "what this project is, in one honest sentence a non-engineer could repeat",
        "what carries risk or key-person dependency, and what remains unknown",
    ],
    "dba": [
        "what data this project owns, and how its schema changes",
        "what would make a migration or a query dangerous here",
    ],
}


def _names(items: list[dict], key: str = "name", limit: int = 12) -> str:
    values = [str(item.get(key, "")) for item in items if item.get(key)]
    head = ", ".join(values[:limit])
    if len(values) > limit:
        head += f", … (+{len(values) - limit} more)"
    return head


def _documents_lines(payload: dict) -> list[str]:
    pages = payload.get("pages", [])
    decisions = payload.get("decisions", [])
    topics = payload.get("topics", [])
    total = len(pages) + len(decisions)
    lines = [f"DOCUMENTATION — {total} page(s), {len(decisions)} of them decision records"]
    if topics:
        areas = ", ".join(
            f"{t['name']} ({t.get('metadata', {}).get('pages', '?')} pages)" for t in topics[:12]
        )
        lines.append(f"  Areas the titles announce: {areas}")
    if decisions:
        lines.append(f"  Decision records: {_names(decisions, limit=10)}")
    if pages:
        lines.append(f"  Example pages: {_names(pages, limit=10)}")
    return lines


def _code_lines(payload: dict) -> list[str]:
    lines = ["CODE"]
    if payload.get("applications"):
        lines.append(f"  Applications: {_names(payload['applications'])}")
    if payload.get("modules"):
        lines.append(f"  Modules ({len(payload['modules'])}): {_names(payload['modules'], limit=8)}")
    if payload.get("dependencies"):
        lines.append(f"  Dependencies: {_names(payload['dependencies'])}")
    return lines


def _tests_lines(payload: dict) -> list[str]:
    return [f"TESTS\n  Suites: {_names(payload.get('suites', []))}"]


def _data_lines(payload: dict) -> list[str]:
    lines = ["DATA"]
    if payload.get("tables"):
        lines.append(f"  Tables ({len(payload['tables'])}): {_names(payload['tables'], limit=15)}")
    if payload.get("migrations"):
        lines.append(f"  Migrations: {len(payload['migrations'])}")
    return lines


def _api_lines(payload: dict) -> list[str]:
    lines = ["API"]
    if payload.get("endpoints"):
        lines.append(
            f"  Endpoints ({len(payload['endpoints'])}): {_names(payload['endpoints'], limit=15)}"
        )
    if payload.get("domain_entities"):
        lines.append(f"  Domain entities: {_names(payload['domain_entities'])}")
    return lines


def _infrastructure_lines(payload: dict) -> list[str]:
    lines = [f"INFRASTRUCTURE\n  Tools: {_names(payload.get('components', []))}"]
    if payload.get("images"):
        lines.append(f"  Container images: {_names(payload['images'])}")
    return lines


def _deployment_lines(payload: dict) -> list[str]:
    return [f"CI/CD\n  Pipelines: {_names(payload.get('pipelines', []))}"]


def _environments_lines(payload: dict) -> list[str]:
    return [
        "ENVIRONMENTS (inferred from directory and file naming, not from a deployment)\n"
        f"  {_names(payload.get('environments', []))}"
    ]


def _risks_lines(payload: dict) -> list[str]:
    findings = payload.get("findings", [])[:6]
    if not findings:
        return []
    lines = ["WHAT THE ANALYZERS FLAGGED"]
    lines += [f"  [{f['severity']}] {f['title']}" for f in findings]
    return lines


def _important_files_lines(payload: dict) -> list[str]:
    files = payload.get("files", [])[:8]
    return [f"KEY FILES\n  {', '.join(f['path'] for f in files)}"] if files else []


def _questions_lines(payload: dict) -> list[str]:
    questions = payload.get("questions", [])
    if not questions:
        return []
    return ["GAPS THE ANALYZERS COULD NOT CLOSE"] + [f"  {q['question']}" for q in questions]


_SECTION_FACTS = {
    Section.DOCUMENTS: _documents_lines,
    Section.CODE: _code_lines,
    Section.TESTS: _tests_lines,
    Section.DATA: _data_lines,
    Section.API: _api_lines,
    Section.INFRASTRUCTURE: _infrastructure_lines,
    Section.DEPLOYMENT: _deployment_lines,
    Section.ENVIRONMENTS: _environments_lines,
    Section.RISKS: _risks_lines,
    Section.IMPORTANT_FILES: _important_files_lines,
    Section.QUESTIONS: _questions_lines,
}


def _facts_block(view: dict) -> str:
    """Everything the analyzers found, and nothing about what they didn't.

    The sections come in the order the role's lens chose, so the model reads a DBA's
    project starting from its tables and a DevOps project starting from its
    infrastructure — the same emphasis the person sees on screen.
    """
    summary = view.get(Section.SUMMARY, {})
    lines: list[str] = [f"WHAT THIS IS: {summary.get('description', '')}".strip()]
    chips = summary.get("technology_chips", [])
    if chips:
        lines.append(f"Technologies named in the files: {', '.join(chips)}")

    for section in view.get("section_order", []):
        render = _SECTION_FACTS.get(section)
        payload = view.get(section)
        if render is None or not isinstance(payload, dict):
            continue
        rendered = render(payload)
        if rendered:
            lines.append("")
            lines.extend(rendered)

    lines.append("")
    lines.append(
        "These facts come from: " + (", ".join(view.get("analyzers_run", [])) or "no analyzer")
    )
    return "\n".join(lines)


def _is_documentation(view: dict) -> bool:
    """A folder of pages, with no code, no infrastructure and no pipelines of its own.

    The distinction matters more than it looks. The pages of such a folder describe a
    system — its queues, its buckets, its databases — that is nowhere in the folder.
    A model that forgets this writes "the project uses AWS S3 and Kafka", which is not
    a fact about the project at all.
    """
    order = view.get("section_order", [])
    has_pages = Section.DOCUMENTS in order
    owns_a_system = any(
        section in order
        for section in (
            Section.CODE,
            Section.INFRASTRUCTURE,
            Section.DEPLOYMENT,
            Section.TESTS,
            Section.API,
            Section.DATA,
        )
    )
    return has_pages and not owns_a_system


def _role_focus(view: dict, role_label: str) -> str:
    questions = _ROLE_QUESTIONS.get(view.get("role", ""), [])
    if not questions:
        return f"You are briefing a {role_label}."
    joined = "; and ".join(questions)
    return (
        f"You are briefing a {role_label} who has just opened this project for the first "
        f"time. What they need from you: {joined}."
    )


def build_ask_graph_prompt(view: dict, role_label: str, question: str) -> str:
    """Answer a free-text question using ONLY the graph facts. If the answer is
    not in the facts, the model must say so rather than guess."""
    return (
        f"You are answering a {role_label}'s question about an unfamiliar software "
        "project. The ONLY information you may use is the FACTS below, which were "
        "extracted deterministically from the project's own files.\n\n"
        "Facts:\n"
        f"{_facts_block(view)}\n\n"
        f"Question: {question}\n\n"
        "Strict rules:\n"
        "- Answer using ONLY the facts above. Do not use outside knowledge or "
        "assumptions about how similar projects usually work.\n"
        "- If the facts do not contain the answer, say plainly: \"That isn't "
        'visible in the analyzed files." — optionally noting what would need to be '
        "checked.\n"
        "- Be concise: 1-4 plain sentences, no markdown, no bullet lists.\n"
        "- Do not invent services, environments, technologies, or risks."
    )


def build_project_intelligence_overview_prompt(view: dict, role_label: str) -> str:
    """The paragraph at the top of Intelligence: the one place the model earns its keep.

    The lists below it are already complete and already correct — repeating them in
    prose would be a waste of the model. What a person cannot get from a list is what
    the shape of these facts *means* for them: what kind of project this is, what
    stands out, and what to look at first. That is what is asked for here, and the
    rules exist so it is asked for without licence to invent.
    """
    rules = [
        "- Use ONLY the facts above. Do not add services, pages, environments, "
        "technologies, dependencies or risks that are not listed — not even ones that "
        "projects like this usually have.",
        "- Do not list things the project does not contain. The facts above are what "
        "exists; silence about everything else is correct.",
        "- Do not restate the lists. The reader can already see them. Say what they "
        "add up to, what stands out, and what deserves attention first.",
        "- Do not assign a role to a tool beyond what the facts state — Terraform and "
        "Terragrunt are infrastructure-as-code, never an 'application framework'.",
        "- Where the facts are thin, say so in the same breath as what you do know, "
        "rather than hedging the whole paragraph.",
        "- Plain sentences: no headings, no bullet lists, no markdown.",
    ]
    if _is_documentation(view):
        rules.insert(
            0,
            "- This project IS a body of documentation. The systems, clouds and "
            "databases named on its pages are things the pages DESCRIBE — they are not "
            "in this folder and you must not attribute them to the project. Write "
            "\"the documentation covers…\", never \"the project uses…\".",
        )
    return (
        f"{_role_focus(view, role_label)}\n\n"
        "Below are FACTS extracted deterministically from the project's own files. They "
        "are the only ground truth you may use.\n\n"
        f"{_facts_block(view)}\n\n"
        "Write 3-5 plain sentences answering exactly what this person needs, in their "
        "language, using these facts.\n\n"
        "Rules:\n" + "\n".join(rules)
    )
