"""Local key-value settings."""

from __future__ import annotations

from app.database import repositories
from app.utils.constants import DEFAULT_SETTINGS


def get_setting(key: str) -> str:
    value = repositories.get_setting(key, DEFAULT_SETTINGS.get(key))
    if value is None:
        return DEFAULT_SETTINGS.get(key, "")
    return value


def get_int(key: str) -> int:
    raw = get_setting(key)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(DEFAULT_SETTINGS.get(key, "0"))


def set_setting(key: str, value: str) -> None:
    repositories.set_setting(key, str(value))


def max_concurrent_browsers() -> int:
    return min(10, max(1, get_int("max_concurrent_browsers")))


def all_settings() -> dict[str, str]:
    return {key: get_setting(key) for key in DEFAULT_SETTINGS}
