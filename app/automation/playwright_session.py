"""Playwright actions used by the replay engine.

Human verification is only detected here. Nothing in this file clicks a
challenge, types a solution, or changes browser identity.
"""

from __future__ import annotations

import time

from app.automation.errors import (
    AutomationError,
    HumanVerificationDetected,
    TargetNotFound,
    VerificationFailed,
)
from app.automation.human_verification import CHALLENGE_PHRASES, CHALLENGE_SELECTORS, MANUAL_REASON
from app.automation.targeting import LocatorPlan, locator_plan
from app.models.workflow import ElementTarget, WorkflowStep
from app.utils.constants import ActionType
from app.utils.logger import get_logger


logger = get_logger("session")


class PlaywrightSession:
    def __init__(self, context) -> None:
        self._context = context
        self._page = context.pages[-1] if context.pages else context.new_page()
        context.on("page", self._on_page)

    def _on_page(self, page) -> None:
        self._page = page

    @property
    def page(self):
        if self._page is None or self._page.is_closed():
            open_pages = [item for item in self._context.pages if not item.is_closed()]
            self._page = open_pages[-1] if open_pages else self._context.new_page()
        return self._page

    def detect_human_verification(self) -> str | None:
        page = self.page
        for selector in CHALLENGE_SELECTORS:
            try:
                locator = page.locator(selector)
                if locator.count() and locator.first.is_visible():
                    return MANUAL_REASON
            except Exception:
                continue
        for phrase in CHALLENGE_PHRASES:
            try:
                locator = page.get_by_text(phrase, exact=False)
                if locator.count() and locator.first.is_visible():
                    return MANUAL_REASON
            except Exception:
                continue
        return None

    def perform(self, step: WorkflowStep, resolved: str, timeout_s: float) -> None:
        if step.action_type in (ActionType.CLICK, ActionType.TYPE, ActionType.PRESS_KEY):
            reason = self.detect_human_verification()
            if reason:
                raise HumanVerificationDetected(reason)
        timeout_ms = max(1, int(timeout_s * 1000))
        page = self.page
        action = step.action_type
        if action in (ActionType.OPEN_URL,):
            url = (resolved or step.value or "").strip()
            if not url:
                raise AutomationError("OPEN_URL is missing a URL")
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            return
        if action == ActionType.NAVIGATE_BACK:
            page.go_back(timeout=timeout_ms, wait_until="domcontentloaded")
            return
        if action == ActionType.NAVIGATE_FORWARD:
            page.go_forward(timeout=timeout_ms, wait_until="domcontentloaded")
            return
        if action == ActionType.RELOAD:
            page.reload(timeout=timeout_ms, wait_until="domcontentloaded")
            return
        if action == ActionType.CLICK:
            self._click(step.target, timeout_ms)
            return
        if action == ActionType.TYPE:
            self._type(step.target, resolved, timeout_ms)
            return
        if action == ActionType.PRESS_KEY:
            page.keyboard.press(resolved or step.value or "Enter")
            return
        if action in (ActionType.WAIT, ActionType.VERIFY):
            return
        raise AutomationError(f"Unsupported action {action}")

    def verify(self, step: WorkflowStep, timeout_s: float) -> None:
        timeout_ms = max(1, int(timeout_s * 1000))
        kind = step.verification_type
        expected = step.verification_expected or ""
        page = self.page
        try:
            if kind == "PAGE_LOADED":
                page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                return
            if kind == "ELEMENT_VISIBLE":
                self._find(self._verification_target(step), timeout_ms, allow_coordinate=False)
                return
            if kind == "ELEMENT_ENABLED":
                locator = self._find(self._verification_target(step), timeout_ms, allow_coordinate=False)
                if isinstance(locator, tuple) or not locator.is_enabled():
                    raise VerificationFailed("Element is not enabled")
                return
            if kind == "TEXT_VISIBLE":
                if not expected:
                    raise VerificationFailed("TEXT_VISIBLE needs the expected text")
                page.get_by_text(expected, exact=False).first.wait_for(state="visible", timeout=timeout_ms)
                return
            if kind == "URL_MATCH":
                if not expected:
                    raise VerificationFailed("URL_MATCH needs the expected text")
                self._wait_for_url(expected, timeout_ms)
                return
            raise VerificationFailed(f"Unknown verification type: {kind}")
        except VerificationFailed:
            raise
        except Exception as exc:
            raise VerificationFailed(str(exc)) from exc

    def locate(self, step: WorkflowStep, timeout_s: float) -> bool:
        try:
            self._find(step.target, max(1, int(timeout_s * 1000)), allow_coordinate=False)
            return True
        except TargetNotFound:
            return False

    def screenshot(self, path: str) -> bool:
        try:
            self.page.screenshot(path=path)
            return True
        except Exception:
            logger.exception("Screenshot failed")
            return False

    def focus(self) -> None:
        self.page.bring_to_front()

    def close(self) -> None:
        return None

    def _verification_target(self, step: WorkflowStep) -> ElementTarget:
        target = step.target
        if any(
            (
                target.role,
                target.label,
                target.placeholder,
                target.selector,
                target.fallback_selector,
                target.test_id,
                target.attributes.get("id"),
            )
        ):
            return target
        expected = step.verification_expected or target.text or target.name
        return ElementTarget(text=expected, name=expected)

    def _wait_for_url(self, expected: str, timeout_ms: int) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        page = self.page
        while time.monotonic() < deadline:
            if expected in (page.url or ""):
                return
            page.wait_for_timeout(200)
        raise VerificationFailed(f'URL "{page.url}" does not contain "{expected}"')

    def _click(self, target: ElementTarget, timeout_ms: int) -> None:
        found = self._find(target, timeout_ms, allow_coordinate=True)
        if isinstance(found, tuple):
            self.page.mouse.click(found[0], found[1])
            return
        found.click(timeout=timeout_ms)

    def _type(self, target: ElementTarget, text: str, timeout_ms: int) -> None:
        found = self._find(target, timeout_ms, allow_coordinate=False)
        if isinstance(found, tuple):
            raise TargetNotFound("Typing needs an element. Coordinates are not used for text input.")
        found.fill(text, timeout=timeout_ms)

    def _find(self, target: ElementTarget, timeout_ms: int, *, allow_coordinate: bool):
        plans = locator_plan(target)
        actionable = [plan for plan in plans if plan.kind != "coordinate"]
        coordinates = [plan for plan in plans if plan.kind == "coordinate"]
        if not actionable:
            if allow_coordinate and coordinates:
                chosen = coordinates[0]
                return (chosen.x, chosen.y)
            raise TargetNotFound("This step has no element selector")
        slice_timeout = max(400, timeout_ms // len(actionable))
        errors: list[str] = []
        for plan in actionable:
            try:
                locator = self._locator(plan)
                if locator.count() == 0:
                    errors.append(f"{plan.kind}: not found")
                    continue
                candidate = locator.first
                candidate.wait_for(state="visible", timeout=slice_timeout)
                return candidate
            except Exception as exc:
                errors.append(f"{plan.kind}: {exc.__class__.__name__}")
        if allow_coordinate and coordinates:
            chosen = coordinates[0]
            return (chosen.x, chosen.y)
        detail = "; ".join(errors[:6])
        raise TargetNotFound(detail or "Element was not found")

    def _locator(self, plan: LocatorPlan):
        page = self.page
        if plan.kind == "role":
            return page.get_by_role(plan.role, name=plan.name)
        if plan.kind == "label":
            return page.get_by_label(plan.value)
        if plan.kind == "placeholder":
            return page.get_by_placeholder(plan.value)
        if plan.kind == "text":
            return page.get_by_text(plan.value, exact=False)
        if plan.kind == "testid":
            return page.get_by_test_id(plan.value)
        if plan.kind == "css":
            return page.locator(plan.value)
        if plan.kind == "xpath":
            value = plan.value
            if not value.startswith("xpath="):
                value = f"xpath={value}"
            return page.locator(value)
        raise TargetNotFound(f"Unsupported locator {plan.kind}")
