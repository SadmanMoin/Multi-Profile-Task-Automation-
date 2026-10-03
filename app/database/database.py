"""Engine, sessions, and schema initialization."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base, SettingRow
from app.utils.constants import DEFAULT_SETTINGS
from app.utils.paths import get_db_path


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def database_url() -> str:
    override = os.environ.get("BTA_DATABASE_URL")
    if override:
        return override
    return f"sqlite:///{get_db_path().as_posix()}"


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
    except Exception:
        return


def init_db(url: str | None = None) -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        return
    chosen = url or database_url()
    connect_args = {"check_same_thread": False, "timeout": 30} if chosen.startswith("sqlite") else {}
    _engine = create_engine(chosen, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    with session_scope() as session:
        for key, value in DEFAULT_SETTINGS.items():
            if session.get(SettingRow, key) is None:
                session.add(SettingRow(key=key, value=value))


def reset_db() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    assert _SessionLocal is not None
    return _SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> None:
    if _SessionLocal is None:
        init_db()
    with session_scope() as session:
        session.execute(text("SELECT 1"))
