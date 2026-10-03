"""Run, log, manual-action, and health-check models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TaskRun(BaseModel):
    id: int | None = None
    workflow_id: int | None = None
    workflow_name: str = ""
    workflow_version: int = 1
    profile_id: int | None = None
    profile_name: str = ""
    status: str
    current_step_number: int = 0
    dry_run: bool = False
    error: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None
    browser_pid: int | None = None


class StepRun(BaseModel):
    id: int | None = None
    task_run_id: int
    step_number: int
    action_type: str
    status: str
    attempt: int = 1
    error: str = ""
    duration_ms: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ActivityLog(BaseModel):
    id: int | None = None
    created_at: datetime | None = None
    profile_name: str = ""
    workflow_name: str = ""
    step_number: int | None = None
    action: str = ""
    status: str = ""
    error: str = ""
    duration_ms: int = 0
    task_run_id: int | None = None


class ManualAction(BaseModel):
    id: int | None = None
    task_run_id: int
    profile_name: str = ""
    workflow_name: str = ""
    step_number: int = 0
    reason: str = ""
    screenshot_path: str = ""
    status: str = "OPEN"
    created_at: datetime | None = None
    resolved_at: datetime | None = None


class CheckResult(BaseModel):
    name: str
    ok: bool
    message: str
    warning: bool = False


class DashboardCounts(BaseModel):
    profiles: int = 0
    running: int = 0
    queued: int = 0
    completed: int = 0
    failed: int = 0
    paused: int = 0
    manual_action_required: int = 0
    stopped: int = 0


class QueuePlan(BaseModel):
    start_ids: list[int] = Field(default_factory=list)
    blocked_ids: list[int] = Field(default_factory=list)
