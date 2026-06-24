"""Prompt for the LLM's plain-language Project Intelligence overview.

The LLM only *explains* facts the deterministic analyzers already established —
it must not invent services, environments, technologies or risks. The facts are
serialized from the presented view (``project_intelligence_view``).
"""

from app.core.domain.role_lens import Section


def _facts_block(view: dict) -> str:
    summary = view.get(Section.SUMMARY, {})
    chips = ", ".join(summary.get("technology_chips", [])) or "none detected"
    counts = summary.get("counts", {})
    envs = [e["name"] for e in view.get(Section.ENVIRONMENTS, {}).get("environments", [])]
    pipelines = [p["name"] for p in view.get(Section.DEPLOYMENT, {}).get("pipelines", [])]
    infra = [c["name"] for c in view.get(Section.INFRASTRUCTURE, {}).get("components", [])]
    top_risks = [
        f"[{f['severity']}] {f['title']}"
        for f in view.get(Section.RISKS, {}).get("findings", [])[:5]
    ]
    lines = [
        f"Technologies detected: {chips}",
        f"Infrastructure tools: {', '.join(infra) or 'none detected'}",
        f"CI/CD pipelines: {', '.join(pipelines) or 'none detected'}",
        f"Environments (inferred from naming): {', '.join(envs) or 'none detected'}",
        f"Counts: services={counts.get('services', 0)}, environments={counts.get('environments', 0)}, "
        f"pipelines={counts.get('pipelines', 0)}, infrastructure={counts.get('infrastructure', 0)}",
        "Top risks: " + ("; ".join(top_risks) if top_risks else "none detected"),
        "Analyzers skipped (technology not detected): "
        + (", ".join(view.get("analyzers_skipped", [])) or "none"),
    ]
    return "\n".join(lines)


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
    return (
        f"You are briefing a {role_label} on an unfamiliar software project. Below are "
        "FACTS extracted deterministically from the project's own files — they are the "
        "only ground truth you may use.\n\n"
        "Facts:\n"
        f"{_facts_block(view)}\n\n"
        "Write a short, plain-language overview (3-5 sentences) of what this project is, "
        "how it appears to be deployed, and what most deserves attention — for the role "
        "above.\n\n"
        "Strict rules:\n"
        "- Use ONLY the facts above. Do not invent services, environments, technologies, "
        "dependencies, or risks that are not listed.\n"
        "- Do NOT assign a role or category to a tool beyond what the facts state. For "
        "example, Terraform and Terragrunt are infrastructure-as-code tools — never call "
        "them an 'application framework' or describe them as application code.\n"
        "- If something is 'none detected', do not claim it exists; you may note it is "
        "not detected if relevant.\n"
        "- No headings, no bullet lists, no markdown — just a few plain sentences.\n"
        "- Do not restate the raw counts mechanically; synthesise them into meaning."
    )
