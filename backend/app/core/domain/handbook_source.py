"""The project handbook is indexed as a pseudo-document under an internal path so
broad "what is this project" questions retrieve it. That path is a machine token,
not something a person should ever see. This module is the single source of truth
for the token and its human-facing label, and the one helper that maps a source
path to what the model (and the user) should read.

Showing the raw token in the grounded prompt made small models echo it verbatim
in prose ("… the README.md and `__project_handbook__` document this"). Presenting
the friendly label instead keeps the answer clean; the citation still resolves
because consumers compare against this same label.
"""

from __future__ import annotations

# Internal path the handbook pseudo-document is stored under (must match the value
# used at index time). Kept here in the domain so prompt/evaluator code can share it
# without importing a use case.
HANDBOOK_SOURCE_PATH = "__project_handbook__"

# What a person (and the model) should see instead of the raw token.
HANDBOOK_DISPLAY_NAME = "Project handbook"


def display_source_path(source_path: str) -> str:
    """Human-facing label for a retrieved source path.

    Returns the friendly handbook label for the handbook pseudo-path; every real
    file path is returned unchanged, so this is a safe no-op everywhere else.
    """
    if source_path == HANDBOOK_SOURCE_PATH:
        return HANDBOOK_DISPLAY_NAME
    return source_path


def is_handbook_source(source_path: str) -> bool:
    return source_path == HANDBOOK_SOURCE_PATH


def mask_handbook_token(text: str) -> str:
    """Replace the raw handbook token wherever it appears in a string (e.g. inside a
    chunk_id like ``w:__project_handbook__:0``) with the friendly label, so the model
    never sees the machine token anywhere in the prompt."""
    if HANDBOOK_SOURCE_PATH not in text:
        return text
    return text.replace(HANDBOOK_SOURCE_PATH, HANDBOOK_DISPLAY_NAME)
