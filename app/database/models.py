"""SQLAlchemy tables. All of this data stays in the local SQLite file."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.timeutil import utcnow


class Base(DeclarativeBase):
    pass


class ProfileRow(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    chrome_executable_path: Mapped[str] = mapped_column(String(1000), default="")
    user_data_dir: Mapped[str] = mapped_column(String(1000), default="")
    chrome_profile_directory: Mapped[str] = mapped_column(String(200), default="Default")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    lock_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock_owner_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock_browser_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock_kind: Mapped[str] = mapped_column(String(40), default="")
    lock_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProfileVariableRow(Base):
    __tablename__ = "profile_variables"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_profile_variable"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowRow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WorkflowStepRow(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_json: Mapped[dict] = mapped_column(JSON, default=dict)
    value: Mapped[str] = mapped_column(Text, default="")
    wait_before_ms: Mapped[int] = mapped_column(Integer, default=0)
    wait_after_ms: Mapped[int] = mapped_column(Integer, default=0)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=15000)
    verification_type: Mapped[str] = mapped_column(String(40), default="")
    verification_expected: Mapped[str] = mapped_column(Text, default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=2)
    retry_delay_ms: Mapped[int] = mapped_column(Integer, default=3000)
    skip_if_already_complete: Mapped[bool] = mapped_column(Boolean, default=False)


class WorkflowVariableRow(Base):
    __tablename__ = "workflow_variables"
    __table_args__ = (UniqueConstraint("workflow_id", "name", name="uq_workflow_variable"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str] = mapped_column(Text, default="")


class WorkflowVersionRow(Base):
    __tablename__ = "workflow_versions"
    __table_args__ = (UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowAssignmentRow(Base):
    __tablename__ = "workflow_assignments"
    __table_args__ = (UniqueConstraint("workflow_id", "profile_id", name="uq_workflow_profile"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)


class TaskRunRow(Base):
    __tablename__ = "task_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int | None] = mapped_column(ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(200), default="")
    workflow_version: Mapped[int] = mapped_column(Integer, default=1)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    profile_name: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(40), default="QUEUED", index=True)
    current_step_number: Mapped[int] = mapped_column(Integer, default=0)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    browser_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)


class StepRunRow(Base):
    __tablename__ = "step_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(40), default="")
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityLogRow(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    profile_name: Mapped[str] = mapped_column(String(200), default="")
    workflow_name: Mapped[str] = mapped_column(String(200), default="")
    step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(40), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    task_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ManualActionRow(Base):
    __tablename__ = "manual_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_run_id: Mapped[int] = mapped_column(ForeignKey("task_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_name: Mapped[str] = mapped_column(String(200), default="")
    workflow_name: Mapped[str] = mapped_column(String(200), default="")
    step_number: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    screenshot_path: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(40), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SettingRow(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
