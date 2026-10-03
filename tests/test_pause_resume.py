import threading
import time

from app.automation.control import RunControl
from app.automation.replay_engine import NullHooks, ReplayEngine
from app.database import repositories
from app.models.workflow import WorkflowStep
from app.services.execution_service import ExecutionService
from app.services.settings_service import set_setting
from app.utils.constants import ActionType, RunStatus
from tests.conftest import make_profile, make_workflow
from tests.fakes import FakeSession


def test_pause_blocks_until_resume():
    session = FakeSession()
    control = RunControl()
    finished = {"done": False}

    def run():
        engine = ReplayEngine(session, control, NullHooks(), {})
        status = engine.run(
            [WorkflowStep(step_number=1, action_type=ActionType.WAIT, value="0.6", retry_count=0)]
        )
        finished["status"] = status
        finished["done"] = True

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.05)
    control.pause()
    time.sleep(0.3)
    assert finished["done"] is False
    control.resume()
    thread.join(timeout=2)
    assert finished["done"] is True
    assert finished["status"] == RunStatus.COMPLETED


def test_stop_ends_the_run():
    session = FakeSession()
    control = RunControl()
    result = {}

    def run():
        engine = ReplayEngine(session, control, NullHooks(), {})
        result["status"] = engine.run(
            [WorkflowStep(step_number=1, action_type=ActionType.WAIT, value="5", retry_count=0)]
        )

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.05)
    control.stop()
    thread.join(timeout=2)
    assert result["status"] == RunStatus.STOPPED


def test_service_pause_resume_and_stop(db):
    set_setting("max_concurrent_browsers", "2")
    profile = make_profile()
    workflow = make_workflow()

    def worker(run_id, control, _service):
        control.checkpoint()
        control.sleep(1.0)
        repositories.finish_run(run_id, RunStatus.COMPLETED, "")

    service = ExecutionService(worker=worker)
    run_id = service.enqueue(workflow.id, [profile.id])[0]
    assert service.kick() == 1
    time.sleep(0.1)
    assert service.pause(run_id) is True
    assert repositories.get_task_run(run_id).status == RunStatus.PAUSED
    time.sleep(0.25)
    assert repositories.get_task_run(run_id).status == RunStatus.PAUSED
    assert service.resume(run_id) is True
    service.join(timeout=2)
    assert repositories.get_task_run(run_id).status == RunStatus.COMPLETED

    def blocking(run_id, control, _service):
        control.sleep(5)
        repositories.finish_run(run_id, RunStatus.COMPLETED, "")

    service = ExecutionService(worker=blocking)
    run_id = service.enqueue(workflow.id, [profile.id])[0]
    service.kick()
    time.sleep(0.1)
    assert service.stop(run_id) is True
    service.join(timeout=2)
    assert repositories.get_task_run(run_id).status == RunStatus.STOPPED
