import time

from app.automation.queue_manager import plan_queue
from app.database import repositories
from app.models.execution import TaskRun
from app.services.execution_service import ExecutionService
from app.services.settings_service import set_setting
from app.utils.constants import RunStatus
from tests.conftest import make_profile, make_workflow


def test_plan_respects_slots_and_one_run_per_profile():
    runs = [
        TaskRun(id=1, profile_id=10, status="QUEUED"),
        TaskRun(id=2, profile_id=10, status="QUEUED"),
        TaskRun(id=3, profile_id=11, status="QUEUED"),
        TaskRun(id=4, profile_id=12, status="QUEUED"),
    ]
    plan = plan_queue(runs, locked_profile_ids=set(), slots=2)
    assert plan.start_ids == [1, 3]
    assert plan.blocked_ids == [2]

    blocked = plan_queue(runs, locked_profile_ids={10}, slots=2)
    assert blocked.start_ids == [3, 4]
    assert blocked.blocked_ids == [1, 2]


def test_same_profile_stays_queued_until_the_first_run_finishes(db):
    set_setting("max_concurrent_browsers", "3")
    profile = make_profile()
    workflow = make_workflow()

    def worker(run_id, _control, _service):
        time.sleep(0.25)
        repositories.finish_run(run_id, RunStatus.COMPLETED, "")

    service = ExecutionService(worker=worker)
    first, second = service.enqueue(workflow.id, [profile.id, profile.id])
    assert service.kick() == 1
    time.sleep(0.05)
    waiting = repositories.get_task_run(second)
    assert repositories.get_task_run(first).status == RunStatus.RUNNING
    assert waiting.status == RunStatus.QUEUED
    assert waiting.error == "Profile currently in use"
    service.join(timeout=2)
    assert service.kick() == 1
    service.join(timeout=2)
    assert repositories.get_task_run(first).status == RunStatus.COMPLETED
    assert repositories.get_task_run(second).status == RunStatus.COMPLETED


def test_stop_queued_run_without_launching(db):
    profile = make_profile()
    workflow = make_workflow()
    service = ExecutionService(worker=lambda *_args: None)
    run_id = service.enqueue(workflow.id, [profile.id])[0]
    assert service.stop(run_id) is True
    assert repositories.get_task_run(run_id).status == RunStatus.STOPPED
    assert service.kick() == 0
