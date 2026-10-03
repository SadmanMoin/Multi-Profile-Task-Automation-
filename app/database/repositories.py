"""Read and write local records. Callers receive plain models, not ORM rows."""

from __future__ import annotations

import json
import os
import threading

from sqlalchemy import delete, func, select, update

from app.database.database import session_scope
from app.database.models import (
    ActivityLogRow,
    ManualActionRow,
    ProfileRow,
    ProfileVariableRow,
    SettingRow,
    StepRunRow,
    TaskRunRow,
    WorkflowAssignmentRow,
    WorkflowRow,
    WorkflowStepRow,
    WorkflowVariableRow,
    WorkflowVersionRow,
)
from app.models.execution import ActivityLog, DashboardCounts, ManualAction, StepRun, TaskRun
from app.models.profile import Profile, ProfileVariable
from app.models.workflow import ElementTarget, Workflow, WorkflowStep, WorkflowVariable
from app.utils.constants import (
    ACTIVE_RUN_STATUSES,
    INTERRUPTED_STATUSES,
    TERMINAL_RUN_STATUSES,
    ManualStatus,
    RunStatus,
)
from app.utils.process import pid_alive
from app.utils.timeutil import as_utc, utcnow


_lock_guard = threading.Lock()


def _json_dict(value) -> dict:
    if not value:
        return {}
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return dict(value)


def _profile(row: ProfileRow) -> Profile:
    return Profile(
        id=row.id,
        name=row.name,
        chrome_executable_path=row.chrome_executable_path,
        user_data_dir=row.user_data_dir,
        chrome_profile_directory=row.chrome_profile_directory,
        enabled=bool(row.enabled),
        notes=row.notes or "",
        created_at=as_utc(row.created_at),
        updated_at=as_utc(row.updated_at),
        lock_run_id=row.lock_run_id,
        lock_owner_pid=row.lock_owner_pid,
        lock_browser_pid=row.lock_browser_pid,
        lock_kind=row.lock_kind or "",
        lock_acquired_at=as_utc(row.lock_acquired_at),
    )


def _step(row: WorkflowStepRow) -> WorkflowStep:
    return WorkflowStep(
        id=row.id,
        workflow_id=row.workflow_id,
        step_number=row.step_number,
        action_type=row.action_type,
        target=ElementTarget.model_validate(_json_dict(row.target_json)),
        value=row.value or "",
        wait_before_ms=row.wait_before_ms or 0,
        wait_after_ms=row.wait_after_ms or 0,
        timeout_ms=row.timeout_ms or 15000,
        verification_type=row.verification_type or "",
        verification_expected=row.verification_expected or "",
        retry_count=row.retry_count if row.retry_count is not None else 2,
        retry_delay_ms=row.retry_delay_ms if row.retry_delay_ms is not None else 3000,
        skip_if_already_complete=bool(row.skip_if_already_complete),
    )


def _workflow(row: WorkflowRow, steps: list[WorkflowStep], variables: list[WorkflowVariable]) -> Workflow:
    return Workflow(
        id=row.id,
        name=row.name,
        description=row.description or "",
        version=row.version or 1,
        created_at=as_utc(row.created_at),
        updated_at=as_utc(row.updated_at),
        steps=steps,
        variables=variables,
    )


def _run(row: TaskRunRow) -> TaskRun:
    return TaskRun(
        id=row.id,
        workflow_id=row.workflow_id,
        workflow_name=row.workflow_name or "",
        workflow_version=row.workflow_version or 1,
        profile_id=row.profile_id,
        profile_name=row.profile_name or "",
        status=row.status,
        current_step_number=row.current_step_number or 0,
        dry_run=bool(row.dry_run),
        error=row.error or "",
        started_at=as_utc(row.started_at),
        finished_at=as_utc(row.finished_at),
        updated_at=as_utc(row.updated_at),
        browser_pid=row.browser_pid,
    )


def _clear_lock(row: ProfileRow) -> None:
    row.lock_run_id = None
    row.lock_owner_pid = None
    row.lock_browser_pid = None
    row.lock_kind = ""
    row.lock_acquired_at = None
    row.updated_at = utcnow()


# --- profiles -----------------------------------------------------------------


def list_profiles() -> list[Profile]:
    with session_scope() as session:
        rows = session.scalars(select(ProfileRow).order_by(ProfileRow.name)).all()
        return [_profile(row) for row in rows]


def get_profile(profile_id: int) -> Profile | None:
    with session_scope() as session:
        row = session.get(ProfileRow, profile_id)
        return _profile(row) if row else None


def profile_name_exists(name: str, ignore_id: int | None = None) -> bool:
    with session_scope() as session:
        query = select(ProfileRow).where(ProfileRow.name == name)
        if ignore_id is not None:
            query = query.where(ProfileRow.id != ignore_id)
        return session.scalars(query).first() is not None


def create_profile(profile: Profile) -> Profile:
    with session_scope() as session:
        now = utcnow()
        row = ProfileRow(
            name=profile.name.strip(),
            chrome_executable_path=profile.chrome_executable_path.strip(),
            user_data_dir=profile.user_data_dir.strip(),
            chrome_profile_directory=profile.chrome_profile_directory.strip() or "Default",
            enabled=profile.enabled,
            notes=profile.notes or "",
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.flush()
        return _profile(row)


def update_profile(profile: Profile) -> Profile:
    with session_scope() as session:
        row = session.get(ProfileRow, profile.id)
        if row is None:
            raise KeyError(profile.id)
        row.name = profile.name.strip()
        row.chrome_executable_path = profile.chrome_executable_path.strip()
        row.user_data_dir = profile.user_data_dir.strip()
        row.chrome_profile_directory = profile.chrome_profile_directory.strip() or "Default"
        row.enabled = profile.enabled
        row.notes = profile.notes or ""
        row.updated_at = utcnow()
        session.flush()
        return _profile(row)


def set_profile_enabled(profile_id: int, enabled: bool) -> None:
    with session_scope() as session:
        row = session.get(ProfileRow, profile_id)
        if row is None:
            raise KeyError(profile_id)
        row.enabled = enabled
        row.updated_at = utcnow()


def delete_profile(profile_id: int) -> None:
    with session_scope() as session:
        session.execute(delete(ProfileVariableRow).where(ProfileVariableRow.profile_id == profile_id))
        session.execute(delete(WorkflowAssignmentRow).where(WorkflowAssignmentRow.profile_id == profile_id))
        session.execute(
            update(TaskRunRow).where(TaskRunRow.profile_id == profile_id).values(profile_id=None)
        )
        session.execute(delete(ProfileRow).where(ProfileRow.id == profile_id))


def count_profiles() -> int:
    with session_scope() as session:
        return int(session.scalar(select(func.count()).select_from(ProfileRow)) or 0)


def acquire_lock(profile_id: int, *, owner_pid: int, run_id: int | None, kind: str) -> bool:
    """Lock a profile for one run, learn session, or test.

    A dead owner is treated as stale and can be replaced. Two live owners cannot
    share the profile.
    """
    with _lock_guard:
        with session_scope() as session:
            row = session.get(ProfileRow, profile_id)
            if row is None:
                return False
            holder = row.lock_owner_pid
            if holder and pid_alive(holder):
                same = holder == owner_pid and row.lock_run_id == run_id and (row.lock_kind or "") == kind
                if not same:
                    return False
            holder_match = (
                ProfileRow.lock_owner_pid.is_(None)
                if holder is None
                else ProfileRow.lock_owner_pid == holder
            )
            result = session.execute(
                update(ProfileRow)
                .where(ProfileRow.id == profile_id)
                .where(holder_match)
                .values(
                    lock_owner_pid=owner_pid,
                    lock_run_id=run_id,
                    lock_kind=kind,
                    lock_browser_pid=None,
                    lock_acquired_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
            return int(result.rowcount or 0) == 1


def release_lock(profile_id: int, *, run_id: int | None = None, kind: str | None = None) -> None:
    with session_scope() as session:
        row = session.get(ProfileRow, profile_id)
        if row is None:
            return
        if run_id is not None and row.lock_run_id != run_id:
            return
        if kind is not None and (row.lock_kind or "") != kind:
            return
        _clear_lock(row)


def release_locks_for_run(run_id: int) -> None:
    with session_scope() as session:
        rows = session.scalars(select(ProfileRow).where(ProfileRow.lock_run_id == run_id)).all()
        for row in rows:
            _clear_lock(row)


def set_lock_browser_pid(profile_id: int, browser_pid: int | None) -> None:
    with session_scope() as session:
        row = session.get(ProfileRow, profile_id)
        if row is None:
            return
        row.lock_browser_pid = browser_pid
        row.updated_at = utcnow()


def list_locked_profiles() -> list[Profile]:
    with session_scope() as session:
        rows = session.scalars(select(ProfileRow).where(ProfileRow.lock_owner_pid.is_not(None))).all()
        return [_profile(row) for row in rows]


def locked_profile_ids() -> set[int]:
    locked: set[int] = set()
    for profile in list_locked_profiles():
        if profile.id is None:
            continue
        if profile.lock_owner_pid and pid_alive(profile.lock_owner_pid):
            locked.add(profile.id)
    return locked


# --- profile variables --------------------------------------------------------


def list_profile_variables(profile_id: int) -> list[ProfileVariable]:
    with session_scope() as session:
        rows = session.scalars(
            select(ProfileVariableRow)
            .where(ProfileVariableRow.profile_id == profile_id)
            .order_by(ProfileVariableRow.name)
        ).all()
        return [
            ProfileVariable(
                id=row.id,
                profile_id=row.profile_id,
                name=row.name,
                is_secret=bool(row.is_secret),
                updated_at=as_utc(row.updated_at),
            )
            for row in rows
        ]


def get_profile_variable_secret(profile_id: int, name: str) -> tuple[str, bool] | None:
    """Return the encrypted token and secret flag. Decrypt only at the call site."""
    with session_scope() as session:
        row = session.scalars(
            select(ProfileVariableRow).where(
                ProfileVariableRow.profile_id == profile_id,
                ProfileVariableRow.name == name,
            )
        ).first()
        if row is None:
            return None
        return row.value_encrypted or "", bool(row.is_secret)


def list_profile_variable_secrets(profile_id: int) -> list[tuple[str, str, bool]]:
    with session_scope() as session:
        rows = session.scalars(
            select(ProfileVariableRow).where(ProfileVariableRow.profile_id == profile_id)
        ).all()
        return [(row.name, row.value_encrypted or "", bool(row.is_secret)) for row in rows]


def upsert_profile_variable(profile_id: int, name: str, encrypted: str, is_secret: bool) -> None:
    with session_scope() as session:
        row = session.scalars(
            select(ProfileVariableRow).where(
                ProfileVariableRow.profile_id == profile_id,
                ProfileVariableRow.name == name,
            )
        ).first()
        if row is None:
            session.add(
                ProfileVariableRow(
                    profile_id=profile_id,
                    name=name,
                    value_encrypted=encrypted,
                    is_secret=is_secret,
                    updated_at=utcnow(),
                )
            )
            return
        if encrypted:
            row.value_encrypted = encrypted
        row.is_secret = is_secret
        row.updated_at = utcnow()


def delete_profile_variable(variable_id: int) -> None:
    with session_scope() as session:
        session.execute(delete(ProfileVariableRow).where(ProfileVariableRow.id == variable_id))


# --- workflows ----------------------------------------------------------------


def _load_steps(session, workflow_id: int) -> list[WorkflowStep]:
    rows = session.scalars(
        select(WorkflowStepRow)
        .where(WorkflowStepRow.workflow_id == workflow_id)
        .order_by(WorkflowStepRow.step_number)
    ).all()
    return [_step(row) for row in rows]


def _load_variables(session, workflow_id: int) -> list[WorkflowVariable]:
    rows = session.scalars(
        select(WorkflowVariableRow)
        .where(WorkflowVariableRow.workflow_id == workflow_id)
        .order_by(WorkflowVariableRow.name)
    ).all()
    return [
        WorkflowVariable(
            id=row.id,
            workflow_id=row.workflow_id,
            name=row.name,
            is_secret=bool(row.is_secret),
            description=row.description or "",
        )
        for row in rows
    ]


def list_workflows() -> list[Workflow]:
    with session_scope() as session:
        rows = session.scalars(select(WorkflowRow).order_by(WorkflowRow.name)).all()
        return [_workflow(row, _load_steps(session, row.id), _load_variables(session, row.id)) for row in rows]


def get_workflow(workflow_id: int) -> Workflow | None:
    with session_scope() as session:
        row = session.get(WorkflowRow, workflow_id)
        if row is None:
            return None
        return _workflow(row, _load_steps(session, row.id), _load_variables(session, row.id))


def create_workflow(name: str, description: str = "") -> Workflow:
    with session_scope() as session:
        now = utcnow()
        row = WorkflowRow(name=name.strip(), description=description or "", version=1, created_at=now, updated_at=now)
        session.add(row)
        session.flush()
        return _workflow(row, [], [])


def update_workflow_meta(workflow_id: int, name: str, description: str) -> None:
    with session_scope() as session:
        row = session.get(WorkflowRow, workflow_id)
        if row is None:
            raise KeyError(workflow_id)
        row.name = name.strip()
        row.description = description or ""
        row.updated_at = utcnow()


def set_workflow_version(workflow_id: int, version: int) -> None:
    with session_scope() as session:
        row = session.get(WorkflowRow, workflow_id)
        if row is None:
            raise KeyError(workflow_id)
        row.version = version
        row.updated_at = utcnow()


def replace_steps(workflow_id: int, steps: list[WorkflowStep]) -> None:
    with session_scope() as session:
        session.execute(delete(WorkflowStepRow).where(WorkflowStepRow.workflow_id == workflow_id))
        for index, step in enumerate(steps, start=1):
            session.add(
                WorkflowStepRow(
                    workflow_id=workflow_id,
                    step_number=index,
                    action_type=step.action_type,
                    target_json=step.target.model_dump(),
                    value=step.value or "",
                    wait_before_ms=max(0, int(step.wait_before_ms)),
                    wait_after_ms=max(0, int(step.wait_after_ms)),
                    timeout_ms=max(0, int(step.timeout_ms)),
                    verification_type=step.verification_type or "",
                    verification_expected=step.verification_expected or "",
                    retry_count=max(0, int(step.retry_count)),
                    retry_delay_ms=max(0, int(step.retry_delay_ms)),
                    skip_if_already_complete=bool(step.skip_if_already_complete),
                )
            )
        row = session.get(WorkflowRow, workflow_id)
        if row is not None:
            row.updated_at = utcnow()


def replace_workflow_variables(workflow_id: int, variables: list[tuple[str, bool]]) -> None:
    with session_scope() as session:
        session.execute(delete(WorkflowVariableRow).where(WorkflowVariableRow.workflow_id == workflow_id))
        for name, is_secret in variables:
            session.add(
                WorkflowVariableRow(
                    workflow_id=workflow_id,
                    name=name,
                    is_secret=is_secret,
                    description="Filled from the profile when the workflow runs.",
                )
            )


def add_workflow_snapshot(workflow: Workflow) -> None:
    with session_scope() as session:
        existing = session.scalars(
            select(WorkflowVersionRow).where(
                WorkflowVersionRow.workflow_id == workflow.id,
                WorkflowVersionRow.version == workflow.version,
            )
        ).first()
        payload = workflow.model_dump(mode="json")
        if existing is None:
            session.add(
                WorkflowVersionRow(
                    workflow_id=workflow.id,
                    version=workflow.version,
                    snapshot_json=payload,
                    created_at=utcnow(),
                )
            )
            return
        existing.snapshot_json = payload
        existing.created_at = utcnow()


def list_workflow_versions(workflow_id: int) -> list[tuple[int, datetime | None]]:
    with session_scope() as session:
        rows = session.scalars(
            select(WorkflowVersionRow)
            .where(WorkflowVersionRow.workflow_id == workflow_id)
            .order_by(WorkflowVersionRow.version)
        ).all()
        return [(row.version, as_utc(row.created_at)) for row in rows]


def get_workflow_snapshot(workflow_id: int, version: int) -> dict | None:
    with session_scope() as session:
        row = session.scalars(
            select(WorkflowVersionRow).where(
                WorkflowVersionRow.workflow_id == workflow_id,
                WorkflowVersionRow.version == version,
            )
        ).first()
        if row is None:
            return None
        return _json_dict(row.snapshot_json)


def delete_workflow(workflow_id: int) -> None:
    with session_scope() as session:
        session.execute(delete(WorkflowStepRow).where(WorkflowStepRow.workflow_id == workflow_id))
        session.execute(delete(WorkflowVariableRow).where(WorkflowVariableRow.workflow_id == workflow_id))
        session.execute(delete(WorkflowVersionRow).where(WorkflowVersionRow.workflow_id == workflow_id))
        session.execute(delete(WorkflowAssignmentRow).where(WorkflowAssignmentRow.workflow_id == workflow_id))
        session.execute(
            update(TaskRunRow).where(TaskRunRow.workflow_id == workflow_id).values(workflow_id=None)
        )
        session.execute(delete(WorkflowRow).where(WorkflowRow.id == workflow_id))


def workflow_has_active_run(workflow_id: int) -> bool:
    with session_scope() as session:
        row = session.scalars(
            select(TaskRunRow).where(
                TaskRunRow.workflow_id == workflow_id,
                TaskRunRow.status.in_(ACTIVE_RUN_STATUSES),
            )
        ).first()
        return row is not None


def set_assignments(workflow_id: int, profile_ids: list[int]) -> None:
    with session_scope() as session:
        session.execute(delete(WorkflowAssignmentRow).where(WorkflowAssignmentRow.workflow_id == workflow_id))
        for profile_id in profile_ids:
            session.add(WorkflowAssignmentRow(workflow_id=workflow_id, profile_id=profile_id))


def list_assigned_profile_ids(workflow_id: int) -> list[int]:
    with session_scope() as session:
        rows = session.scalars(
            select(WorkflowAssignmentRow.profile_id).where(WorkflowAssignmentRow.workflow_id == workflow_id)
        ).all()
        return [int(row) for row in rows]


# --- runs ---------------------------------------------------------------------


def create_task_run(
    *,
    workflow_id: int,
    workflow_name: str,
    workflow_version: int,
    profile_id: int,
    profile_name: str,
    dry_run: bool,
) -> TaskRun:
    with session_scope() as session:
        now = utcnow()
        row = TaskRunRow(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            profile_id=profile_id,
            profile_name=profile_name,
            status=RunStatus.QUEUED,
            dry_run=dry_run,
            error="",
            updated_at=now,
        )
        session.add(row)
        session.flush()
        return _run(row)


def get_task_run(run_id: int) -> TaskRun | None:
    with session_scope() as session:
        row = session.get(TaskRunRow, run_id)
        return _run(row) if row else None


def list_task_runs(limit: int = 300) -> list[TaskRun]:
    with session_scope() as session:
        rows = session.scalars(select(TaskRunRow).order_by(TaskRunRow.id.desc()).limit(limit)).all()
        return [_run(row) for row in rows]


def list_queued_runs() -> list[TaskRun]:
    with session_scope() as session:
        rows = session.scalars(
            select(TaskRunRow).where(TaskRunRow.status == RunStatus.QUEUED).order_by(TaskRunRow.id)
        ).all()
        return [_run(row) for row in rows]


def count_runs_with_status(statuses: tuple[str, ...] | list[str]) -> int:
    with session_scope() as session:
        value = session.scalar(
            select(func.count()).select_from(TaskRunRow).where(TaskRunRow.status.in_(tuple(statuses)))
        )
        return int(value or 0)


def dashboard_counts() -> DashboardCounts:
    with session_scope() as session:
        def _count(status: str) -> int:
            return int(
                session.scalar(
                    select(func.count()).select_from(TaskRunRow).where(TaskRunRow.status == status)
                )
                or 0
            )

        return DashboardCounts(
            profiles=int(session.scalar(select(func.count()).select_from(ProfileRow)) or 0),
            running=_count(RunStatus.RUNNING),
            queued=_count(RunStatus.QUEUED),
            completed=_count(RunStatus.COMPLETED),
            failed=_count(RunStatus.FAILED),
            paused=_count(RunStatus.PAUSED),
            manual_action_required=_count(RunStatus.MANUAL_ACTION_REQUIRED),
            stopped=_count(RunStatus.STOPPED),
        )


def mark_run_running(run_id: int) -> None:
    with session_scope() as session:
        row = session.get(TaskRunRow, run_id)
        if row is None:
            return
        now = utcnow()
        row.status = RunStatus.RUNNING
        row.error = ""
        row.started_at = row.started_at or now
        row.updated_at = now


def set_run_status(run_id: int, status: str, error: str | None = None) -> None:
    with session_scope() as session:
        row = session.get(TaskRunRow, run_id)
        if row is None:
            return
        row.status = status
        if error is not None:
            row.error = error
        row.updated_at = utcnow()


def set_run_error(run_id: int, error: str) -> None:
    with session_scope() as session:
        row = session.get(TaskRunRow, run_id)
        if row is None or (row.error or "") == error:
            return
        row.error = error
        row.updated_at = utcnow()


def set_run_step(run_id: int, step_number: int) -> None:
    with session_scope() as session:
        row = session.get(TaskRunRow, run_id)
        if row is None:
            return
        row.current_step_number = step_number
        row.updated_at = utcnow()


def set_run_browser_pid(run_id: int, browser_pid: int | None) -> None:
    with session_scope() as session:
        row = session.get(TaskRunRow, run_id)
        if row is None:
            return
        row.browser_pid = browser_pid
        row.updated_at = utcnow()


def finish_run(run_id: int, status: str, error: str = "") -> None:
    with session_scope() as session:
        row = session.get(TaskRunRow, run_id)
        if row is None or row.status in TERMINAL_RUN_STATUSES:
            return
        row.status = status
        row.error = error or ""
        row.finished_at = utcnow()
        row.updated_at = row.finished_at


def list_unfinished_runs() -> list[TaskRun]:
    with session_scope() as session:
        rows = session.scalars(
            select(TaskRunRow).where(TaskRunRow.status.in_(INTERRUPTED_STATUSES)).order_by(TaskRunRow.id)
        ).all()
        return [_run(row) for row in rows]


def upsert_step_run(
    *,
    task_run_id: int,
    step_number: int,
    action_type: str,
    status: str,
    attempt: int,
    error: str,
    duration_ms: int,
) -> None:
    with session_scope() as session:
        row = session.scalars(
            select(StepRunRow).where(
                StepRunRow.task_run_id == task_run_id,
                StepRunRow.step_number == step_number,
            )
        ).first()
        now = utcnow()
        if row is None:
            session.add(
                StepRunRow(
                    task_run_id=task_run_id,
                    step_number=step_number,
                    action_type=action_type,
                    status=status,
                    attempt=attempt,
                    error=error or "",
                    duration_ms=duration_ms,
                    started_at=now,
                    finished_at=now,
                )
            )
            return
        row.action_type = action_type
        row.status = status
        row.attempt = attempt
        row.error = error or ""
        row.duration_ms = duration_ms
        row.finished_at = now
        if row.started_at is None:
            row.started_at = now


def list_step_runs(task_run_id: int) -> list[StepRun]:
    with session_scope() as session:
        rows = session.scalars(
            select(StepRunRow).where(StepRunRow.task_run_id == task_run_id).order_by(StepRunRow.step_number)
        ).all()
        return [
            StepRun(
                id=row.id,
                task_run_id=row.task_run_id,
                step_number=row.step_number,
                action_type=row.action_type,
                status=row.status,
                attempt=row.attempt,
                error=row.error or "",
                duration_ms=row.duration_ms or 0,
                started_at=as_utc(row.started_at),
                finished_at=as_utc(row.finished_at),
            )
            for row in rows
        ]


# --- activity and manual actions ---------------------------------------------


def add_activity(
    *,
    profile_name: str,
    workflow_name: str,
    step_number: int | None,
    action: str,
    status: str,
    error: str = "",
    duration_ms: int = 0,
    task_run_id: int | None = None,
) -> None:
    with session_scope() as session:
        session.add(
            ActivityLogRow(
                created_at=utcnow(),
                profile_name=profile_name,
                workflow_name=workflow_name,
                step_number=step_number,
                action=action,
                status=status,
                error=error or "",
                duration_ms=duration_ms,
                task_run_id=task_run_id,
            )
        )


def list_activity(limit: int = 1000) -> list[ActivityLog]:
    with session_scope() as session:
        rows = session.scalars(select(ActivityLogRow).order_by(ActivityLogRow.id.desc()).limit(limit)).all()
        return [
            ActivityLog(
                id=row.id,
                created_at=as_utc(row.created_at),
                profile_name=row.profile_name or "",
                workflow_name=row.workflow_name or "",
                step_number=row.step_number,
                action=row.action or "",
                status=row.status or "",
                error=row.error or "",
                duration_ms=row.duration_ms or 0,
                task_run_id=row.task_run_id,
            )
            for row in rows
        ]


def create_manual_action(
    *,
    task_run_id: int,
    profile_name: str,
    workflow_name: str,
    step_number: int,
    reason: str,
    screenshot_path: str,
) -> ManualAction:
    with session_scope() as session:
        row = ManualActionRow(
            task_run_id=task_run_id,
            profile_name=profile_name,
            workflow_name=workflow_name,
            step_number=step_number,
            reason=reason,
            screenshot_path=screenshot_path,
            status=ManualStatus.OPEN,
            created_at=utcnow(),
        )
        session.add(row)
        session.flush()
        return ManualAction(
            id=row.id,
            task_run_id=row.task_run_id,
            profile_name=row.profile_name,
            workflow_name=row.workflow_name,
            step_number=row.step_number,
            reason=row.reason,
            screenshot_path=row.screenshot_path,
            status=row.status,
            created_at=as_utc(row.created_at),
        )


def list_manual_actions(open_only: bool = False) -> list[ManualAction]:
    with session_scope() as session:
        query = select(ManualActionRow).order_by(ManualActionRow.id.desc())
        if open_only:
            query = query.where(ManualActionRow.status == ManualStatus.OPEN)
        rows = session.scalars(query).all()
        return [
            ManualAction(
                id=row.id,
                task_run_id=row.task_run_id,
                profile_name=row.profile_name or "",
                workflow_name=row.workflow_name or "",
                step_number=row.step_number or 0,
                reason=row.reason or "",
                screenshot_path=row.screenshot_path or "",
                status=row.status,
                created_at=as_utc(row.created_at),
                resolved_at=as_utc(row.resolved_at),
            )
            for row in rows
        ]


def resolve_manual_actions(task_run_id: int, status: str = ManualStatus.RESOLVED) -> None:
    with session_scope() as session:
        rows = session.scalars(
            select(ManualActionRow).where(
                ManualActionRow.task_run_id == task_run_id,
                ManualActionRow.status == ManualStatus.OPEN,
            )
        ).all()
        now = utcnow()
        for row in rows:
            row.status = status
            row.resolved_at = now


# --- settings -----------------------------------------------------------------


def get_setting(key: str, default: str | None = None) -> str | None:
    with session_scope() as session:
        row = session.get(SettingRow, key)
        if row is None:
            return default
        return row.value


def set_setting(key: str, value: str) -> None:
    with session_scope() as session:
        row = session.get(SettingRow, key)
        if row is None:
            session.add(SettingRow(key=key, value=value))
            return
        row.value = value


def current_owner_pid() -> int:
    return os.getpid()
