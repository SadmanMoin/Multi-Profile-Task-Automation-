"""Local data locations. Everything the app stores stays under the data directory."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    override = os.environ.get("BTA_DATA_DIR")
    path = Path(override) if override else PROJECT_ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    return get_data_dir() / "app.db"


def get_logs_dir() -> Path:
    path = get_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_workflows_dir() -> Path:
    path = get_data_dir() / "workflows"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_screenshots_dir() -> Path:
    path = get_data_dir() / "screenshots"
    path.mkdir(parents=True, exist_ok=True)
    return path
