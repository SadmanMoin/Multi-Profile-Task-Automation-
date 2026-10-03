"""Checks that must pass before a profile runs a workflow."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from app.database.database import check_database
from app.models.execution import CheckResult
from app.models.profile import Profile
from app.models.workflow import Workflow
from app.utils.paths import get_data_dir
from app.utils.process import pid_alive


DiskUsage = Callable[[str], object]


def _locked_by_someone_else(profile: Profile, allow_run_id: int | None) -> bool:
    if not profile.lock_owner_pid or not pid_alive(profile.lock_owner_pid):
        return False
    if allow_run_id is not None and profile.lock_run_id == allow_run_id:
        return False
    return True


def run_health_checks(
    profile: Profile,
    workflow: Workflow | None,
    *,
    min_free_mb: int = 500,
    allow_run_id: int | None = None,
    disk_usage: DiskUsage = shutil.disk_usage,
    database_check: Callable[[], None] = check_database,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    executable = Path(profile.chrome_executable_path)
    results.append(
        CheckResult(
            name="Chrome executable",
            ok=executable.is_file(),
            message="Found" if executable.is_file() else f"Chrome executable not found: {executable}",
        )
    )
    user_data = Path(profile.user_data_dir)
    data_ok = user_data.is_dir()
    results.append(
        CheckResult(
            name="Profile path",
            ok=data_ok,
            message="Found" if data_ok else f"Profile path not found: {user_data}",
        )
    )
    profile_dir = user_data / (profile.chrome_profile_directory or "Default")
    if data_ok and not profile_dir.exists():
        results.append(
            CheckResult(
                name="Chrome profile directory",
                ok=True,
                warning=True,
                message=(
                    f"{profile.chrome_profile_directory} was not found in the user data directory. "
                    "Chrome may create it, but an existing logged-in profile should already be there."
                ),
            )
        )
    else:
        results.append(
            CheckResult(
                name="Chrome profile directory",
                ok=True,
                message="Found" if profile_dir.exists() else "Not checked",
            )
        )
    in_use = _locked_by_someone_else(profile, allow_run_id)
    results.append(
        CheckResult(
            name="Profile lock",
            ok=not in_use,
            message="Available" if not in_use else "Profile currently in use",
        )
    )
    results.append(
        CheckResult(
            name="Profile enabled",
            ok=bool(profile.enabled),
            message="Enabled" if profile.enabled else "Profile is disabled",
        )
    )
    try:
        database_check()
        results.append(CheckResult(name="Database", ok=True, message="Available"))
    except Exception as exc:
        results.append(CheckResult(name="Database", ok=False, message=f"Database unavailable: {exc}"))
    try:
        usage = disk_usage(str(get_data_dir()))
        free_mb = float(usage.free) / (1024 * 1024)
        enough = free_mb >= min_free_mb
        results.append(
            CheckResult(
                name="Disk space",
                ok=enough,
                message=f"{free_mb:.0f} MB free (minimum {min_free_mb} MB)",
            )
        )
    except Exception as exc:
        results.append(CheckResult(name="Disk space", ok=False, message=f"Could not check disk space: {exc}"))
    if workflow is None or not workflow.steps:
        results.append(CheckResult(name="Workflow", ok=False, message="Workflow is missing or has no steps"))
    else:
        results.append(
            CheckResult(
                name="Workflow",
                ok=True,
                message=f"{workflow.name} v{workflow.version} ({len(workflow.steps)} steps)",
            )
        )
    singleton = user_data / "SingletonLock"
    if data_ok and singleton.exists():
        results.append(
            CheckResult(
                name="Chrome session",
                ok=True,
                warning=True,
                message="Chrome looks open for this user data directory. Close it or the launch can fail.",
            )
        )
    return results


def health_ok(results: list[CheckResult]) -> bool:
    return all(item.ok for item in results)


def health_summary(results: list[CheckResult]) -> str:
    lines = []
    for item in results:
        if item.warning and item.ok:
            state = "WARNING"
        else:
            state = "OK" if item.ok else "FAIL"
        lines.append(f"[{state}] {item.name}: {item.message}")
    return "\n".join(lines)
