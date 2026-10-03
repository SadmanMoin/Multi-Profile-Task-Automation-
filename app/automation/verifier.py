"""Decide whether a step's expected state is present."""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.constants import VerificationType


@dataclass
class Observation:
    page_loaded: bool = False
    url: str = ""
    element_visible: bool = False
    element_enabled: bool = False
    text_visible: bool = False
    error: str = ""


def assess(verification_type: str, expected: str, observation: Observation) -> tuple[bool, str]:
    """Return (passed, message). This does not interact with the page."""
    kind = verification_type or VerificationType.NONE
    if kind == VerificationType.NONE:
        return True, "No verification"
    if kind == VerificationType.PAGE_LOADED:
        if observation.page_loaded:
            return True, "Page loaded"
        return False, observation.error or "Page did not load"
    if kind == VerificationType.ELEMENT_VISIBLE:
        if observation.element_visible:
            return True, "Element is visible"
        return False, observation.error or "Element is not visible"
    if kind == VerificationType.ELEMENT_ENABLED:
        if observation.element_visible and observation.element_enabled:
            return True, "Element is enabled"
        if not observation.element_visible:
            return False, observation.error or "Element is not visible"
        return False, observation.error or "Element is not enabled"
    if kind == VerificationType.TEXT_VISIBLE:
        if observation.text_visible:
            return True, "Expected text is visible"
        return False, observation.error or f'Expected text not visible: "{expected}"'
    if kind == VerificationType.URL_MATCH:
        if expected and expected in (observation.url or ""):
            return True, "URL matched"
        return False, observation.error or f'URL "{observation.url}" does not contain "{expected}"'
    return False, f"Unknown verification type: {kind}"
