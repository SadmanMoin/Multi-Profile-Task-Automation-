"""Statuses, action types, and defaults shared across the app."""

from __future__ import annotations


class ActionType:
    OPEN_URL = "OPEN_URL"
    CLICK = "CLICK"
    TYPE = "TYPE"
    PRESS_KEY = "PRESS_KEY"
    NAVIGATE_BACK = "NAVIGATE_BACK"
    NAVIGATE_FORWARD = "NAVIGATE_FORWARD"
    RELOAD = "RELOAD"
    WAIT = "WAIT"
    VERIFY = "VERIFY"


ACTION_TYPES = (
    ActionType.OPEN_URL,
    ActionType.CLICK,
    ActionType.TYPE,
    ActionType.PRESS_KEY,
    ActionType.NAVIGATE_BACK,
    ActionType.NAVIGATE_FORWARD,
    ActionType.RELOAD,
    ActionType.WAIT,
    ActionType.VERIFY,
)

MUTATING_ACTIONS = (
    ActionType.CLICK,
    ActionType.TYPE,
    ActionType.PRESS_KEY,
)


class RunStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"
    STOPPED = "STOPPED"


RUN_STATUSES = (
    RunStatus.QUEUED,
    RunStatus.RUNNING,
    RunStatus.PAUSED,
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.MANUAL_ACTION_REQUIRED,
    RunStatus.STOPPED,
)

ACTIVE_RUN_STATUSES = (
    RunStatus.QUEUED,
    RunStatus.RUNNING,
    RunStatus.PAUSED,
    RunStatus.MANUAL_ACTION_REQUIRED,
)

SLOT_STATUSES = (
    RunStatus.RUNNING,
    RunStatus.PAUSED,
    RunStatus.MANUAL_ACTION_REQUIRED,
)

TERMINAL_RUN_STATUSES = (
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.STOPPED,
)

INTERRUPTED_STATUSES = (
    RunStatus.RUNNING,
    RunStatus.PAUSED,
    RunStatus.MANUAL_ACTION_REQUIRED,
)


class StepStatus:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRY = "RETRY"
    SKIPPED_ALREADY_COMPLETED = "SKIPPED_ALREADY_COMPLETED"
    RUNNING = "RUNNING"


class VerificationType:
    NONE = ""
    PAGE_LOADED = "PAGE_LOADED"
    ELEMENT_VISIBLE = "ELEMENT_VISIBLE"
    ELEMENT_ENABLED = "ELEMENT_ENABLED"
    TEXT_VISIBLE = "TEXT_VISIBLE"
    URL_MATCH = "URL_MATCH"


VERIFICATION_TYPES = (
    VerificationType.NONE,
    VerificationType.PAGE_LOADED,
    VerificationType.ELEMENT_VISIBLE,
    VerificationType.ELEMENT_ENABLED,
    VerificationType.TEXT_VISIBLE,
    VerificationType.URL_MATCH,
)


class LockKind:
    RUN = "run"
    LEARN = "learn"
    TEST = "test"


class ManualStatus:
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


PROFILE_IN_USE_MESSAGE = "Profile currently in use"

INTERRUPTED_MESSAGE = (
    "Interrupted by application shutdown or crash. "
    "The browser session was closed. Start the workflow again."
)

DEFAULT_SETTINGS = {
    "max_concurrent_browsers": "3",
    "default_timeout_ms": "15000",
    "default_retry_count": "2",
    "default_retry_delay_ms": "3000",
    "min_free_disk_mb": "500",
    "schema_version": "1",
}

NAV_ITEMS = (
    "Dashboard",
    "Profiles",
    "Workflows",
    "Learn Mode",
    "Runs",
    "Logs",
    "Settings",
)
