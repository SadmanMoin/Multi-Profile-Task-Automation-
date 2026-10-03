"""Clean up after a crash.

Interrupted runs are marked failed, stale profile locks are released, and
orphaned automation Chrome processes we started are closed. Chrome user data
is never deleted.
"""

from __future__ import annotations

import os

from app.database import repositories
from app.services.logging_service import record
from app.utils.constants import INTERRUPTED_MESSAGE, RunStatus
from app.utils.logger import get_logger
from app.utils.process import pid_alive, terminate_automation_chrome


logger = get_logger("recovery")


def _owner_is_another_live_app(owner_pid: int | None) -> bool:
    return bool(owner_pid and owner_pid != os.getpid() and pid_alive(owner_pid))


def recover_on_startup() -> list[str]:
    messages: list[str] = []
    unfinished = repositories.list_unfinished_runs()
    handled_profiles: set[int] = set()
    for run in unfinished:
        profile = repositories.get_profile(run.profile_id) if run.profile_id else None
        owner = profile.lock_owner_pid if profile else None
        if _owner_is_another_live_app(owner):
            messages.append(f"{run.profile_name} is in use by another running copy of the app. Left it alone.")
            continue
        if profile is not None and run.browser_pid:
            closed = terminate_automation_chrome(run.browser_pid, profile.user_data_dir)
            if closed:
                messages.append(f"Closed orphaned Chrome for {run.profile_name}.")
        if run.id is not None:
            repositories.finish_run(run.id, RunStatus.FAILED, INTERRUPTED_MESSAGE)
            record(
                profile_name=run.profile_name,
                workflow_name=run.workflow_name,
                step_number=run.current_step_number or None,
                action="RECOVER",
                status=RunStatus.FAILED,
                error=INTERRUPTED_MESSAGE,
                task_run_id=run.id,
            )
        if run.profile_id is not None:
            repositories.release_lock(run.profile_id)
            handled_profiles.add(run.profile_id)
        messages.append(
            f"{run.profile_name or 'Profile'} / {run.workflow_name or 'workflow'} was interrupted and marked FAILED."
        )

    for profile in repositories.list_locked_profiles():
        if profile.id in handled_profiles or profile.id is None:
            continue
        if _owner_is_another_live_app(profile.lock_owner_pid):
            continue
        if profile.lock_browser_pid:
            closed = terminate_automation_chrome(profile.lock_browser_pid, profile.user_data_dir)
            if closed:
                messages.append(f"Closed orphaned Chrome for {profile.name}.")
        repositories.release_lock(profile.id)
        messages.append(f"Released stale lock on {profile.name}.")
    if messages:
        logger.warning("Startup recovery: %s", " | ".join(messages))
    else:
        logger.info("Startup recovery found nothing to clean up")
    return messages
