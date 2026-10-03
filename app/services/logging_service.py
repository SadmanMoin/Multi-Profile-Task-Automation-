"""Workflow activity log. Application diagnostics go to the log file instead."""

from __future__ import annotations

import csv
from pathlib import Path

from app.database import repositories
from app.models.execution import ActivityLog
from app.utils.logger import get_logger
from app.utils.redact import redact_text
from app.utils.timeutil import format_local


logger = get_logger("activity")

CSV_HEADERS = (
    "timestamp",
    "profile",
    "workflow",
    "step",
    "action",
    "status",
    "error",
    "duration_ms",
)


def record(
    *,
    profile_name: str = "",
    workflow_name: str = "",
    step_number: int | None = None,
    action: str = "",
    status: str = "",
    error: str = "",
    duration_ms: int = 0,
    task_run_id: int | None = None,
) -> None:
    safe_error = redact_text(error)
    safe_action = redact_text(action)
    repositories.add_activity(
        profile_name=profile_name,
        workflow_name=workflow_name,
        step_number=step_number,
        action=safe_action,
        status=status,
        error=safe_error,
        duration_ms=max(0, int(duration_ms)),
        task_run_id=task_run_id,
    )
    logger.info(
        "profile=%s workflow=%s step=%s action=%s status=%s duration_ms=%s error=%s",
        profile_name,
        workflow_name,
        step_number if step_number is not None else "",
        safe_action,
        status,
        duration_ms,
        safe_error,
    )


def recent(limit: int = 500) -> list[ActivityLog]:
    return repositories.list_activity(limit=limit)


def export_csv(path: Path, limit: int = 100000) -> int:
    rows = repositories.list_activity(limit=limit)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_HEADERS)
        for row in reversed(rows):
            writer.writerow(
                [
                    format_local(row.created_at),
                    row.profile_name,
                    row.workflow_name,
                    "" if row.step_number is None else row.step_number,
                    row.action,
                    row.status,
                    row.error,
                    row.duration_ms,
                ]
            )
    return len(rows)
