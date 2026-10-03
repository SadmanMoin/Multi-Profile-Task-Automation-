import os
import subprocess
import sys
from pathlib import Path

from app.database.database import session_scope
from app.database.models import ProfileRow
from app.database.repositories import create_task_run, get_profile, get_task_run
from app.services.recovery_service import recover_on_startup
from app.utils.constants import RunStatus
from tests.conftest import make_profile, make_workflow


def _mark_running(profile_id: int, workflow, browser_pid: int, owner_pid: int) -> int:
    run = create_task_run(
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        workflow_version=workflow.version,
        profile_id=profile_id,
        profile_name="Profile",
        dry_run=False,
    )
    from app.database.repositories import set_run_browser_pid, set_run_status

    set_run_status(run.id, RunStatus.RUNNING)
    set_run_browser_pid(run.id, browser_pid)
    with session_scope() as session:
        row = session.get(ProfileRow, profile_id)
        row.lock_owner_pid = owner_pid
        row.lock_run_id = run.id
        row.lock_kind = "run"
        row.lock_browser_pid = browser_pid
        row.user_data_dir = str(Path(row.user_data_dir))
    return run.id


def test_crash_recovery_marks_the_run_failed_and_keeps_profile_data(db, tmp_path):
    user_data = tmp_path / "User Data"
    user_data.mkdir()
    marker = user_data / "keep-me.txt"
    marker.write_text("cookies stay", encoding="utf-8")
    profile = make_profile(user_data_dir=str(user_data))
    workflow = make_workflow()
    run_id = _mark_running(profile.id, workflow, browser_pid=os.getpid(), owner_pid=99999999)
    messages = recover_on_startup()
    recovered = get_task_run(run_id)
    assert recovered.status == RunStatus.FAILED
    assert "Interrupted" in recovered.error
    assert get_profile(profile.id).lock_owner_pid is None
    assert marker.read_text(encoding="utf-8") == "cookies stay"
    assert user_data.is_dir()
    assert any("FAILED" in message or "interrupted" in message.lower() for message in messages)


def test_recovery_leaves_a_live_other_instance_alone(db):
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        profile = make_profile()
        workflow = make_workflow()
        run_id = _mark_running(profile.id, workflow, browser_pid=None, owner_pid=process.pid)
        recover_on_startup()
        assert get_task_run(run_id).status == RunStatus.RUNNING
        assert get_profile(profile.id).lock_owner_pid == process.pid
    finally:
        process.terminate()
        process.wait(timeout=5)
