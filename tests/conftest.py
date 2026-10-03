"""Isolated SQLite data directory for every test."""

from __future__ import annotations

import pytest

from app.database.database import init_db, reset_db
from app.models.profile import Profile
from app.models.workflow import ElementTarget, Workflow, WorkflowStep
from app.services.profile_service import create_profile
from app.services.workflow_service import save_workflow
from app.utils.constants import ActionType, VerificationType


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("BTA_DATA_DIR", str(tmp_path))
    reset_db()
    init_db()
    yield tmp_path
    reset_db()


def make_profile(name: str = "Profile 01", **overrides) -> Profile:
    payload = Profile(
        name=name,
        chrome_executable_path=overrides.pop("chrome_executable_path", r"C:\Chrome\chrome.exe"),
        user_data_dir=overrides.pop("user_data_dir", r"C:\Chrome\User Data"),
        chrome_profile_directory=overrides.pop("chrome_profile_directory", "Default"),
        enabled=overrides.pop("enabled", True),
        notes=overrides.pop("notes", ""),
    )
    return create_profile(payload)


def make_workflow(name: str = "Project A Daily Task", steps: list[WorkflowStep] | None = None) -> Workflow:
    if steps is None:
        steps = [
            WorkflowStep(step_number=1, action_type=ActionType.OPEN_URL, value="https://example.test"),
            WorkflowStep(
                step_number=2,
                action_type=ActionType.CLICK,
                target=ElementTarget(role="button", name="Connect", selector="#connect"),
                verification_type=VerificationType.TEXT_VISIBLE,
                verification_expected="Completed",
            ),
        ]
    return save_workflow(Workflow(name=name, description="Demo"), steps)
