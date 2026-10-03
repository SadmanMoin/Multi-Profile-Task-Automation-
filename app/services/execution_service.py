"""Queue runs, enforce the concurrency limit, and drive the replay engine."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from datetime import datetime

from app.automation.browser_manager import BrowserManager
from app.automation.control import RunControl
from app.automation.errors import ProfileInUse, StopRequested
from app.automation.health_checker import health_ok, health_summary, run_health_checks
from app.automation.playwright_session import PlaywrightSession
from app.automation.queue_manager import plan_queue
from app.automation.replay_engine import ReplayEngine
from app.automation.secrets import is_secret_variable
from app.database import repositories
from app.models.workflow import WorkflowStep
from app.services import logging_service, profile_service, settings_service, workflow_service
from app.services.errors import ServiceError
from app.utils.constants import (
    PROFILE_IN_USE_MESSAGE,
    SLOT_STATUSES,
    LockKind,
    RunStatus,
    StepStatus,
)
from app.utils.logger import get_logger
from app.utils.paths import get_screenshots_dir
from app.utils.redact import redact_known_secrets, redact_text


logger = get_logger("execution")

Listener = Callable[[str, str], None]
Worker = Callable[[int, RunControl, "ExecutionService"], None]


class DbHooks:
    """Write step progress without ever recording secret values."""

    def __init__(self, run_id: int, service: "ExecutionService", secret_values: list[str]) -> None:
        self.run_id = run_id
        self.service = service
        self.secret_values = secret_values
        run = repositories.get_task_run(run_id)
        self.profile_name = run.profile_name if run else ""
        self.workflow_name = run.workflow_name if run else ""
        self.profile_id = run.profile_id if run else None

    def _error(self, error: str) -> str:
        return redact_known_secrets(error, self.secret_values)[:2000]

    def _activity(self, step: WorkflowStep | None, action: str, status: str, error: str = "", duration_ms: int = 0) -> None:
        logging_service.record(
            profile_name=self.profile_name,
            workflow_name=self.workflow_name,
            step_number=None if step is None else step.step_number,
            action=action,
            status=status,
            error=self._error(error),
            duration_ms=duration_ms,
            task_run_id=self.run_id,
        )

    def step_started(self, step: WorkflowStep) -> None:
        repositories.set_run_step(self.run_id, step.step_number)
        repositories.upsert_step_run(
            task_run_id=self.run_id,
            step_number=step.step_number,
            action_type=step.action_type,
            status=StepStatus.RUNNING,
            attempt=1,
            error="",
            duration_ms=0,
        )

    def step_succeeded(self, step: WorkflowStep, duration_ms: int, attempt: int) -> None:
        repositories.upsert_step_run(
            task_run_id=self.run_id,
            step_number=step.step_number,
            action_type=step.action_type,
            status=StepStatus.SUCCESS,
            attempt=attempt,
            error="",
            duration_ms=duration_ms,
        )
        self._activity(step, step.action_type, StepStatus.SUCCESS, duration_ms=duration_ms)

    def step_retry(self, step: WorkflowStep, attempt: int, error: str) -> None:
        repositories.upsert_step_run(
            task_run_id=self.run_id,
            step_number=step.step_number,
            action_type=step.action_type,
            status=StepStatus.RETRY,
            attempt=attempt,
            error=self._error(error),
            duration_ms=0,
        )
        self._activity(step, step.action_type, StepStatus.RETRY, error=error)

    def step_failed(self, step: WorkflowStep, error: str) -> None:
        safe = self._error(error)
        repositories.upsert_step_run(
            task_run_id=self.run_id,
            step_number=step.step_number,
            action_type=step.action_type,
            status=StepStatus.FAILED,
            attempt=step.retry_count + 1,
            error=safe,
            duration_ms=0,
        )
        repositories.set_run_error(self.run_id, safe)
        self._activity(step, step.action_type, StepStatus.FAILED, error=safe)

    def step_skipped(self, step: WorkflowStep) -> None:
        repositories.upsert_step_run(
            task_run_id=self.run_id,
            step_number=step.step_number,
            action_type=step.action_type,
            status=StepStatus.SKIPPED_ALREADY_COMPLETED,
            attempt=1,
            error="",
            duration_ms=0,
        )
        self._activity(step, step.action_type, StepStatus.SKIPPED_ALREADY_COMPLETED)

    def manual_action(self, step: WorkflowStep, reason: str) -> None:
        safe_reason = self._error(reason) or "Human verification detected"
        screenshot = ""
        session = self.service.session_for(self.run_id)
        if session is not None:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            path = get_screenshots_dir() / f"run{self.run_id}-step{step.step_number}-{stamp}.png"
            if session.screenshot(str(path)):
                screenshot = str(path)
        repositories.create_manual_action(
            task_run_id=self.run_id,
            profile_name=self.profile_name,
            workflow_name=self.workflow_name,
            step_number=step.step_number,
            reason=safe_reason,
            screenshot_path=screenshot,
        )
        repositories.set_run_status(self.run_id, RunStatus.MANUAL_ACTION_REQUIRED, safe_reason)
        self._activity(step, step.action_type, RunStatus.MANUAL_ACTION_REQUIRED, error=safe_reason)
        self.service.emit(
            RunStatus.MANUAL_ACTION_REQUIRED,
            f"{self.profile_name} / {self.workflow_name} / step {step.step_number}: {safe_reason}",
        )

    def refresh_variables(self) -> tuple[dict[str, str], list[str]]:
        if self.profile_id is None:
            return {}, []
        values = profile_service.load_variable_values(self.profile_id)
        secrets = [value for name, value in values.items() if is_secret_variable(name)]
        self.secret_values = secrets
        return values, secrets


class ExecutionService:
    def __init__(self, worker: Worker | None = None) -> None:
        self._worker = worker or self._run_workflow
        self._controls: dict[int, RunControl] = {}
        self._sessions: dict[int, object] = {}
        self._threads: list[threading.Thread] = []
        self._guard = threading.Lock()
        self._kick_lock = threading.Lock()
        self._stop_queue = threading.Event()
        self._queue_thread: threading.Thread | None = None
        self._listeners: list[Listener] = []

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def emit(self, status: str, message: str) -> None:
        for listener in list(self._listeners):
            try:
                listener(status, message)
            except Exception:
                logger.exception("Run listener failed")

    def session_for(self, run_id: int):
        with self._guard:
            return self._sessions.get(run_id)

    def start(self) -> None:
        if self._queue_thread and self._queue_thread.is_alive():
            return
        self._stop_queue.clear()
        self._queue_thread = threading.Thread(target=self._loop, name="bta-queue", daemon=True)
        self._queue_thread.start()

    def shutdown(self) -> None:
        self._stop_queue.set()
        with self._guard:
            controls = list(self._controls.values())
        for control in controls:
            control.stop()
        self.join(timeout=3)
        for run in repositories.list_unfinished_runs():
            profile = repositories.get_profile(run.profile_id) if run.profile_id else None
            if run.browser_pid and profile is not None:
                from app.utils.process import terminate_automation_chrome

                terminate_automation_chrome(run.browser_pid, profile.user_data_dir)
            if run.id is not None:
                repositories.finish_run(run.id, RunStatus.STOPPED, "Stopped during application exit")
            if run.profile_id is not None:
                repositories.release_lock(run.profile_id)
        self.join(timeout=2)

    def join(self, timeout: float | None = None) -> None:
        for thread in list(self._threads):
            if thread is threading.current_thread():
                continue
            thread.join(timeout=timeout)

    def active_count(self) -> int:
        return repositories.count_runs_with_status(
            [
                RunStatus.QUEUED,
                RunStatus.RUNNING,
                RunStatus.PAUSED,
                RunStatus.MANUAL_ACTION_REQUIRED,
            ]
        )

    def enqueue(self, workflow_id: int, profile_ids: list[int], *, dry_run: bool = False) -> list[int]:
        workflow = workflow_service.get_workflow(workflow_id)
        if not workflow.steps:
            raise ServiceError("Workflow has no steps")
        if not profile_ids:
            raise ServiceError("Select at least one profile")
        run_ids: list[int] = []
        for profile_id in profile_ids:
            profile = profile_service.get_profile(profile_id)
            if not profile.enabled:
                raise ServiceError(f"{profile.name} is disabled")
            run = repositories.create_task_run(
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                workflow_version=workflow.version,
                profile_id=profile.id,
                profile_name=profile.name,
                dry_run=dry_run,
            )
            logging_service.record(
                profile_name=profile.name,
                workflow_name=workflow.name,
                action="QUEUE",
                status=RunStatus.QUEUED,
                task_run_id=run.id,
            )
            if run.id is not None:
                run_ids.append(run.id)
        logger.info("Queued %s run(s) for workflow %s dry_run=%s", len(run_ids), workflow.name, dry_run)
        return run_ids

    def kick(self) -> int:
        """Start as many queued runs as the concurrency limit allows."""
        with self._kick_lock:
            slots = settings_service.max_concurrent_browsers() - repositories.count_runs_with_status(SLOT_STATUSES)
            queued = repositories.list_queued_runs()
            plan = plan_queue(queued, repositories.locked_profile_ids(), max(0, slots))
            for run_id in plan.blocked_ids:
                repositories.set_run_error(run_id, PROFILE_IN_USE_MESSAGE)
            threads: list[threading.Thread] = []
            for run_id in plan.start_ids:
                thread = self._prepare_run(run_id)
                if thread is not None:
                    threads.append(thread)
        for thread in threads:
            thread.start()
        return len(threads)

    def _prepare_run(self, run_id: int) -> threading.Thread | None:
        run = repositories.get_task_run(run_id)
        if run is None or run.profile_id is None or run.status != RunStatus.QUEUED:
            return None
        if not repositories.acquire_lock(
            run.profile_id,
            owner_pid=os.getpid(),
            run_id=run_id,
            kind=LockKind.RUN,
        ):
            repositories.set_run_error(run_id, PROFILE_IN_USE_MESSAGE)
            return None
        repositories.mark_run_running(run_id)
        control = RunControl()
        thread = threading.Thread(
            target=self._thread_main,
            args=(run_id, control),
            name=f"bta-run-{run_id}",
            daemon=True,
        )
        with self._guard:
            self._controls[run_id] = control
            self._threads.append(thread)
        return thread

    def _thread_main(self, run_id: int, control: RunControl) -> None:
        try:
            self._worker(run_id, control, self)
        except StopRequested:
            repositories.finish_run(run_id, RunStatus.STOPPED, "")
        except Exception as exc:
            message = redact_text(str(exc)) or "Run failed"
            logger.exception("Run %s crashed", run_id)
            repositories.finish_run(run_id, RunStatus.FAILED, message)
            self.emit(RunStatus.FAILED, message)
        finally:
            repositories.release_locks_for_run(run_id)
            with self._guard:
                self._controls.pop(run_id, None)
                self._sessions.pop(run_id, None)

    def _loop(self) -> None:
        while not self._stop_queue.is_set():
            try:
                self.kick()
            except Exception:
                logger.exception("Queue tick failed")
            self._stop_queue.wait(0.4)

    def pause(self, run_id: int) -> bool:
        run = repositories.get_task_run(run_id)
        if run is None or run.status != RunStatus.RUNNING:
            return False
        control = self._controls.get(run_id)
        if control is None:
            return False
        control.pause()
        repositories.set_run_status(run_id, RunStatus.PAUSED)
        logging_service.record(
            profile_name=run.profile_name,
            workflow_name=run.workflow_name,
            step_number=run.current_step_number or None,
            action="PAUSE",
            status=RunStatus.PAUSED,
            task_run_id=run_id,
        )
        return True

    def resume(self, run_id: int) -> bool:
        run = repositories.get_task_run(run_id)
        if run is None or run.status not in (RunStatus.PAUSED, RunStatus.MANUAL_ACTION_REQUIRED):
            return False
        control = self._controls.get(run_id)
        if control is None:
            return False
        control.resume()
        repositories.set_run_status(run_id, RunStatus.RUNNING, "")
        repositories.resolve_manual_actions(run_id)
        logging_service.record(
            profile_name=run.profile_name,
            workflow_name=run.workflow_name,
            step_number=run.current_step_number or None,
            action="RESUME",
            status=RunStatus.RUNNING,
            task_run_id=run_id,
        )
        return True

    def stop(self, run_id: int) -> bool:
        run = repositories.get_task_run(run_id)
        if run is None or run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED):
            return False
        control = self._controls.get(run_id)
        if control is None:
            repositories.finish_run(run_id, RunStatus.STOPPED, "")
            if run.profile_id is not None:
                repositories.release_lock(run.profile_id, run_id=run_id)
            logging_service.record(
                profile_name=run.profile_name,
                workflow_name=run.workflow_name,
                action="STOP",
                status=RunStatus.STOPPED,
                task_run_id=run_id,
            )
            return True
        control.stop()
        return True

    def focus(self, run_id: int) -> None:
        control = self._controls.get(run_id)
        if control is None:
            raise ServiceError("Browser is not open for this run")
        control.request_focus()

    def _register_session(self, run_id: int, session) -> None:
        with self._guard:
            self._sessions[run_id] = session

    def _run_workflow(self, run_id: int, control: RunControl, service: "ExecutionService") -> None:
        run = repositories.get_task_run(run_id)
        if run is None or run.profile_id is None or run.workflow_id is None:
            repositories.finish_run(run_id, RunStatus.FAILED, "Run is missing its profile or workflow")
            return
        profile = repositories.get_profile(run.profile_id)
        workflow = repositories.get_workflow(run.workflow_id)
        if profile is None or workflow is None:
            repositories.finish_run(run_id, RunStatus.FAILED, "Profile or workflow no longer exists")
            self.emit(RunStatus.FAILED, f"{run.profile_name} / {run.workflow_name} failed")
            return
        checks = run_health_checks(
            profile,
            workflow,
            min_free_mb=settings_service.get_int("min_free_disk_mb"),
            allow_run_id=run_id,
        )
        if not health_ok(checks):
            message = health_summary(checks)
            repositories.finish_run(run_id, RunStatus.FAILED, message)
            self.emit(RunStatus.FAILED, f"{profile.name} / {workflow.name} failed the health check")
            return
        browser = BrowserManager()
        try:
            context = browser.launch(profile)
            session = PlaywrightSession(context)
            service._register_session(run_id, session)

            def pump() -> None:
                while True:
                    try:
                        command = control.commands.get_nowait()
                    except Exception:
                        return
                    if command == "focus":
                        try:
                            session.focus()
                        except Exception:
                            logger.exception("Could not focus the browser")

            control.on_pump = pump
            pid = browser.find_pid(profile)
            if pid:
                repositories.set_run_browser_pid(run_id, pid)
                repositories.set_lock_browser_pid(profile.id, pid)
            values = profile_service.load_variable_values(profile.id)
            secrets = [value for name, value in values.items() if is_secret_variable(name)]
            hooks = DbHooks(run_id, service, secrets)
            engine = ReplayEngine(
                session,
                control,
                hooks,
                values,
                dry_run=run.dry_run,
                secret_values=secrets,
            )
            logger.info(
                "Run %s started profile=%s workflow=%s dry_run=%s",
                run_id,
                profile.name,
                workflow.name,
                run.dry_run,
            )
            result = engine.run(workflow.steps)
            error = ""
            if result == RunStatus.FAILED:
                latest = repositories.get_task_run(run_id)
                error = latest.error if latest else "Step failed"
            repositories.finish_run(run_id, result, error)
            logging_service.record(
                profile_name=profile.name,
                workflow_name=workflow.name,
                action="RUN",
                status=result,
                error=error,
                task_run_id=run_id,
            )
            if result == RunStatus.FAILED:
                service.emit(RunStatus.FAILED, f"{profile.name} / {workflow.name} failed")
        except ProfileInUse as exc:
            repositories.finish_run(run_id, RunStatus.FAILED, str(exc))
            service.emit(RunStatus.FAILED, f"{profile.name}: {exc}")
        except StopRequested:
            repositories.finish_run(run_id, RunStatus.STOPPED, "")
        except Exception as exc:
            message = redact_text(str(exc)) or "Run failed"
            repositories.finish_run(run_id, RunStatus.FAILED, message)
            service.emit(RunStatus.FAILED, f"{profile.name} / {workflow.name}: {message}")
        finally:
            browser.close()


_service: ExecutionService | None = None
_service_lock = threading.Lock()


def get_execution_service() -> ExecutionService:
    global _service
    with _service_lock:
        if _service is None:
            _service = ExecutionService()
        return _service


def reset_execution_service() -> None:
    global _service
    with _service_lock:
        if _service is not None:
            _service.shutdown()
        _service = None


def open_manual_actions():
    return repositories.list_manual_actions(open_only=True)
