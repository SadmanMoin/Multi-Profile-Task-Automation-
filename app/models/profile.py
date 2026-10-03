"""Chrome profile and per-profile variable models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Profile(BaseModel):
    id: int | None = None
    name: str
    chrome_executable_path: str
    user_data_dir: str
    chrome_profile_directory: str = "Default"
    enabled: bool = True
    notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    lock_run_id: int | None = None
    lock_owner_pid: int | None = None
    lock_browser_pid: int | None = None
    lock_kind: str = ""
    lock_acquired_at: datetime | None = None


class ProfileVariable(BaseModel):
    id: int | None = None
    profile_id: int
    name: str
    is_secret: bool = False
    updated_at: datetime | None = None
