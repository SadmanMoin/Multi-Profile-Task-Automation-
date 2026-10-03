"""Automation errors. None of these are used to defeat site protections."""

from __future__ import annotations


class AutomationError(Exception):
    """A workflow step or browser launch failed."""


class TargetNotFound(AutomationError):
    """No reliable locator matched the recorded element."""


class VerificationFailed(AutomationError):
    """The step ran, but its verification did not pass."""


class HumanVerificationDetected(AutomationError):
    """A human check is on screen. The app stops and waits for the user."""

    def __init__(self, reason: str = "Human verification detected") -> None:
        self.reason = reason
        super().__init__(reason)


class MissingVariable(AutomationError):
    """A {{NAME}} placeholder has no value on the selected profile."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Missing profile variable {{{{{name}}}}}")


class ProfileInUse(AutomationError):
    """The Chrome profile is locked by another run or by Chrome itself."""

    def __init__(self, message: str = "Profile currently in use") -> None:
        super().__init__(message)


class StopRequested(Exception):
    """The user stopped the run. This is not a failure."""
