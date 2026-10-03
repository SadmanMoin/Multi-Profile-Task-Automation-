"""UTC timestamps and local display formatting."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_local(value: datetime | None, with_date: bool = True) -> str:
    aware = as_utc(value)
    if aware is None:
        return ""
    local = aware.astimezone()
    if with_date:
        return local.strftime("%Y-%m-%d %H:%M:%S")
    return local.strftime("%H:%M:%S")
