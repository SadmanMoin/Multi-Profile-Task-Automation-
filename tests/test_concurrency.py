import threading
import time

from app.database import repositories
from app.services.execution_service import ExecutionService
from app.services.settings_service import set_setting
from app.utils.constants import RunStatus
from tests.conftest import make_profile, make_workflow


def test_concurrency_limit_is_enforced(db):
    set_setting("max_concurrent_browsers", "2")
    profiles = [make_profile(f"Profile {index}") for index in range(1, 5)]
    workflow = make_workflow()
    state = {"current": 0, "max": 0}
    lock = threading.Lock()

    def worker(run_id, _control, _service):
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        time.sleep(0.25)
        with lock:
            state["current"] -= 1
        repositories.finish_run(run_id, RunStatus.COMPLETED, "")

    service = ExecutionService(worker=worker)
    service.enqueue(workflow.id, [profile.id for profile in profiles])
    deadline = time.time() + 5
    active = [RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.PAUSED, RunStatus.MANUAL_ACTION_REQUIRED]
    while repositories.count_runs_with_status(active) and time.time() < deadline:
        service.kick()
        time.sleep(0.05)
    service.join(timeout=2)
    assert state["max"] <= 2
    assert state["max"] >= 1
    assert repositories.dashboard_counts().completed == 4
    assert repositories.dashboard_counts().running == 0
