"""The folder is the backup. There is no export, deliberately.

An export would produce a second copy in a format of our own devising, which then
has to stay correct forever. The folder is already the real thing: a person who
can see it can copy it, move it to another machine, or hand it to whatever backup
they already trust. So the app's whole contribution is showing them where it is.
"""

from pathlib import Path

from app.api.routes import local_data_safety


def test_reading_the_path_does_not_open_anything():
    """The GET is a question, not an action. Opening a Finder window because a
    settings screen was rendered would be the app doing something nobody asked."""
    opened: list[Path] = []
    original = local_data_safety._open_in_file_manager
    local_data_safety._open_in_file_manager = lambda path: opened.append(path) or ""
    try:
        response = local_data_safety.get_data_folder()
    finally:
        local_data_safety._open_in_file_manager = original

    assert response.path
    assert opened == []
    assert response.opened is False


def test_opening_reports_the_folder_it_opened():
    calls: list[Path] = []
    original = local_data_safety._open_in_file_manager

    def _fake(path):
        calls.append(path)
        return ""

    local_data_safety._open_in_file_manager = _fake
    try:
        settings_path = local_data_safety.get_settings().app_data_dir.expanduser()
        settings_path.mkdir(parents=True, exist_ok=True)
        response = local_data_safety.open_data_folder()
    finally:
        local_data_safety._open_in_file_manager = original

    assert response.opened is True
    assert response.error == ""
    assert calls == [settings_path]


def test_a_folder_that_does_not_exist_yet_says_so_instead_of_failing():
    """On a fresh install there is nothing to open, and that is not an error —
    it is the true state of a person who has not saved anything yet."""
    original_settings = local_data_safety.get_settings

    class _Settings:
        app_data_dir = Path("/nonexistent-data-folder-for-this-test")

    local_data_safety.get_settings = lambda: _Settings()
    try:
        response = local_data_safety.open_data_folder()
    finally:
        local_data_safety.get_settings = original_settings

    assert response.exists is False
    assert response.opened is False
    assert "does not exist yet" in response.error
