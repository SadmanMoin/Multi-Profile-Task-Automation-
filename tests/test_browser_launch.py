"""Private Chrome copies for Learn Mode, never the daily User Data folder."""

import pytest

from app.automation.browser_manager import (
    PLAYWRIGHT_ARGS_TO_DROP,
    _remove_launch_dir,
    is_system_chrome_user_data,
    launch_error,
    resolve_launch_dirs,
)
from app.automation.errors import AutomationError, ProfileInUse
from app.models.profile import Profile


def test_system_chrome_user_data_is_detected(monkeypatch, tmp_path):
    chrome_home = tmp_path / "Google" / "Chrome" / "User Data"
    chrome_home.mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert is_system_chrome_user_data(chrome_home)
    assert not is_system_chrome_user_data(tmp_path / "other")


def test_selected_chrome_profile_is_copied_not_linked(monkeypatch, tmp_path, db):
    local = tmp_path / "local"
    chrome_home = local / "Google" / "Chrome" / "User Data"
    source_profile = chrome_home / "Profile 3"
    source_profile.mkdir(parents=True)
    (source_profile / "Cookies").write_text("session", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    profile = Profile(
        id=7,
        name="Shop login",
        chrome_executable_path=str(tmp_path / "chrome.exe"),
        user_data_dir=str(chrome_home),
        chrome_profile_directory="Profile 3",
    )
    dest, directory = resolve_launch_dirs(profile)
    assert directory == "Profile 3"
    assert dest != chrome_home
    assert not dest.is_junction()
    assert dest.resolve() != chrome_home.resolve()
    assert (dest / "Profile 3" / "Cookies").read_text(encoding="utf-8") == "session"
    (source_profile / "Cookies").write_text("changed", encoding="utf-8")
    dest_again, directory_again = resolve_launch_dirs(profile)
    assert dest_again == dest
    assert directory_again == "Profile 3"
    assert (dest_again / "Profile 3" / "Cookies").read_text(encoding="utf-8") == "session"


def test_remove_launch_dir_refuses_real_chrome_folder(monkeypatch, tmp_path):
    chrome_home = tmp_path / "Google" / "Chrome" / "User Data"
    chrome_home.mkdir(parents=True)
    (chrome_home / "keep.txt").write_text("safe", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(AutomationError, match="Refusing to delete"):
        _remove_launch_dir(chrome_home)
    assert (chrome_home / "keep.txt").read_text(encoding="utf-8") == "safe"


def test_launch_timeout_becomes_a_short_message():
    error = launch_error(RuntimeError(": Timeout 60000ms exceeded.\nCall log:\n  - <launching> chrome.exe"))
    assert isinstance(error, AutomationError)
    assert "Call log" not in str(error)
    assert "could not connect" in str(error)


def test_profile_in_use_stays_profile_in_use():
    error = launch_error(RuntimeError("Opening in existing browser session"))
    assert isinstance(error, ProfileInUse)


def test_playwright_drop_list_keeps_debugging_pipe():
    assert "--remote-debugging-pipe" not in PLAYWRIGHT_ARGS_TO_DROP
    assert "--user-data-dir" not in PLAYWRIGHT_ARGS_TO_DROP
    assert "--no-sandbox" in PLAYWRIGHT_ARGS_TO_DROP
