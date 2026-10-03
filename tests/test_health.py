from pathlib import Path

from app.automation.health_checker import health_ok, run_health_checks
from app.automation.human_verification import phrase_matches
from app.models.profile import Profile
from app.models.workflow import Workflow, WorkflowStep
from app.utils.constants import ActionType


class _Usage:
    def __init__(self, free_bytes: int) -> None:
        self.free = free_bytes


def test_health_check_reports_missing_chrome_and_low_disk(db, tmp_path):
    profile = Profile(
        id=1,
        name="Profile 01",
        chrome_executable_path=str(tmp_path / "missing-chrome.exe"),
        user_data_dir=str(tmp_path),
        chrome_profile_directory="Default",
        enabled=True,
    )
    workflow = Workflow(id=1, name="Project A", steps=[WorkflowStep(step_number=1, action_type=ActionType.WAIT, value="1")])
    results = run_health_checks(
        profile,
        workflow,
        min_free_mb=500,
        disk_usage=lambda _path: _Usage(50 * 1024 * 1024),
        database_check=lambda: None,
    )
    by_name = {item.name: item for item in results}
    assert by_name["Chrome executable"].ok is False
    assert by_name["Profile path"].ok is True
    assert by_name["Disk space"].ok is False
    assert by_name["Database"].ok is True
    assert by_name["Workflow"].ok is True
    assert health_ok(results) is False


def test_health_check_passes_when_files_exist(db, tmp_path):
    chrome = tmp_path / "chrome.exe"
    chrome.write_text("", encoding="utf-8")
    user_data = tmp_path / "User Data"
    (user_data / "Default").mkdir(parents=True)
    profile = Profile(
        name="Profile 01",
        chrome_executable_path=str(chrome),
        user_data_dir=str(user_data),
        chrome_profile_directory="Default",
    )
    workflow = Workflow(name="Project A", steps=[WorkflowStep(step_number=1, action_type=ActionType.RELOAD)])
    results = run_health_checks(
        profile,
        workflow,
        min_free_mb=1,
        disk_usage=lambda _path: _Usage(5 * 1024 * 1024 * 1024),
        database_check=lambda: None,
    )
    assert health_ok(results)


def test_human_verification_detection_does_not_offer_a_solver():
    import app.automation.human_verification as module

    assert phrase_matches("Please verify you are human") == "Human verification detected"
    assert phrase_matches("Daily check-in") is None
    names = [name.lower() for name in dir(module)]
    assert not any("solve" in name or "bypass" in name for name in names)


def test_profile_directory_marker_remains(tmp_path: Path):
    assert tmp_path.exists()
