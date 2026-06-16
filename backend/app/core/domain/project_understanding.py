from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProjectRisk:
    """A single detected risk or gap, ideally citing the source file it came from."""

    text: str
    source_file: str | None = None


@dataclass(frozen=True)
class ProjectStartPoint:
    """A file a newcomer should read, with a one-line reason, in reading order."""

    file: str
    reason: str


@dataclass(frozen=True)
class ProjectRunCommand:
    """A setup/run/test command grounded in the project's docs or config."""

    command: str
    note: str = ""


@dataclass(frozen=True)
class ProjectUnderstanding:
    """A grounded, plain-language understanding of a workspace project.

    ``model`` is the provider/model string that produced the summary (e.g.
    ``"fake/fake-llm"``) so the frontend can detect staleness when the selected
    LLM later changes. ``index_signature`` identifies the index/scan version the
    understanding was built from. ``sources`` lists the file paths whose chunks
    were actually used as evidence.

    The optional guide sections (``architecture``, ``start_here``,
    ``run_commands``) are grounded extras shown on the project's Home view.
    """

    workspace_id: str
    model: str
    generated_at: str
    index_signature: str
    summary: str
    risks: list[ProjectRisk] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    architecture: str = ""
    start_here: list[ProjectStartPoint] = field(default_factory=list)
    run_commands: list[ProjectRunCommand] = field(default_factory=list)
