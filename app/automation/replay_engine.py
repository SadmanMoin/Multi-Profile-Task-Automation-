"""Replay a saved workflow one step at a time.

The engine does not solve CAPTCHAs. When a human check is visible it pauses
and waits for Resume.
"""

from __future__ import annotations

import time
from typing import Protocol

from app.automation.control import RunControl
from app.automation.errors import (
    HumanVerificationDetected,
    MissingVariable,
    StopRequested,
    TargetNotFound,
    VerificationFailed,
)
from app.automation.retry_manager import policy_for
from app.automation.secrets import resolve_template
from app.models.workflow import WorkflowStep
from app.utils.constants import MUTATING_ACTIONS, ActionType, RunStatus
from app.utils.redact import redact_known_secrets


class ReplayHooks(Protocol):
    def step_started(self, step: WorkflowStep) -> None: ...

    def step_succeeded(self, step: WorkflowStep, duration_ms: int, attempt: int) -> None: ...

    def step_retry(self, step: WorkflowStep, attempt: int, error: str) -> None: ...

    def step_failed(self, step: WorkflowStep, error: str) -> None: ...

    def step_skipped(self, step: WorkflowStep) -> None: ...

    def manual_action(self, step: WorkflowStep, reason: str) -> None: ...


class NullHooks:
    def step_started(self, step: WorkflowStep) -> None:
        return None

    def step_succeeded(self, step: WorkflowStep, duration_ms: int, attempt: int) -> None:
        return None

    def step_retry(self, step: WorkflowStep, attempt: int, error: str) -> None:
        return None

    def step_failed(self, step: WorkflowStep, error: str) -> None:
        return None

    def step_skipped(self, step: WorkflowStep) -> None:
        return None

    def manual_action(self, step: WorkflowStep, reason: str) -> None:
        return None


class ReplayEngine:
    def __init__(
        self,
        session,
        control: RunControl,
        hooks: ReplayHooks | None = None,
        variables: dict[str, str] | None = None,
        *,
        dry_run: bool = False,
        secret_values: list[str] | None = None,
    ) -> None:
        self.session = session
        self.control = control
        self.hooks: ReplayHooks = hooks or NullHooks()
        self.variables = dict(variables or {})
        self.dry_run = dry_run
        self.secret_values = [value for value in (secret_values or []) if value]

    def run(self, steps: list[WorkflowStep]) -> str:
        try:
            for step in steps:
                self.control.checkpoint()
                if self._run_step(step) == "fail":
                    return RunStatus.FAILED
            return RunStatus.COMPLETED
        except StopRequested:
            return RunStatus.STOPPED

    def _safe(self, message: str) -> str:
        return redact_known_secrets(message, self.secret_values)[:2000]

    def _reload_variables(self) -> None:
        refresher = getattr(self.hooks, "refresh_variables", None)
        if not refresher:
            return
        values, secrets = refresher()
        self.variables = dict(values)
        self.secret_values = [value for value in secrets if value]

    def _pause_for_person(self, step: WorkflowStep, reason: str) -> None:
        self.control.request_manual()
        self.hooks.manual_action(step, reason)
        self.control.wait_manual()

    def _human_reason(self) -> str | None:
        detected = self.session.detect_human_verification()
        return detected or None

    def _resolve(self, step: WorkflowStep) -> str:
        if step.action_type in (ActionType.OPEN_URL, ActionType.TYPE, ActionType.PRESS_KEY, ActionType.WAIT):
            return resolve_template(step.value, self.variables)
        return step.value

    def _act(self, step: WorkflowStep, resolved: str) -> None:
        if step.action_type == ActionType.WAIT:
            self.control.sleep(_wait_seconds(step, resolved))
            return
        if step.action_type == ActionType.VERIFY:
            if not step.verification_type:
                raise VerificationFailed("VERIFY step has no verification type")
            self.session.verify(step, step.timeout_ms / 1000)
            return
        if self.dry_run and step.action_type in MUTATING_ACTIONS:
            if not self.session.locate(step, step.timeout_ms / 1000):
                raise TargetNotFound("Target was not found during dry run")
            return
        self.session.perform(step, resolved, step.timeout_ms / 1000)

    def _run_step(self, step: WorkflowStep) -> str:
        self.hooks.step_started(step)
        if step.skip_if_already_complete and step.verification_type:
            try:
                self.session.verify(step, min(step.timeout_ms, 3000) / 1000)
            except VerificationFailed:
                pass
            else:
                self.hooks.step_skipped(step)
                return "ok"

        policy = policy_for(step.retry_count, step.retry_delay_ms)
        attempt = 1
        acted = False
        while attempt <= policy.max_attempts:
            self.control.checkpoint()
            started = time.monotonic()
            try:
                reason = self._human_reason()
                if reason:
                    raise HumanVerificationDetected(reason)
                if not acted:
                    self.control.sleep(max(0, step.wait_before_ms) / 1000)
                    self.control.checkpoint()
                    resolved = self._resolve(step)
                    self._act(step, resolved)
                    acted = True
                reason = self._human_reason()
                if reason:
                    raise HumanVerificationDetected(reason)
                if step.verification_type and step.action_type != ActionType.VERIFY:
                    self.session.verify(step, step.timeout_ms / 1000)
                self.control.sleep(max(0, step.wait_after_ms) / 1000)
                duration = int((time.monotonic() - started) * 1000)
                self.hooks.step_succeeded(step, duration, attempt)
                return "ok"
            except StopRequested:
                raise
            except HumanVerificationDetected as exc:
                # Keep `acted` so a check that appears after a click is not submitted twice.
                self._pause_for_person(step, exc.reason or "Human verification detected")
                continue
            except MissingVariable as exc:
                acted = False
                self._pause_for_person(
                    step,
                    f"Missing profile variable {{{{{exc.name}}}}}. Add it on the profile, then resume.",
                )
                self._reload_variables()
                continue
            except Exception as exc:
                acted = False
                message = self._safe(str(exc)) or exc.__class__.__name__
                if not policy.should_retry(attempt):
                    self.hooks.step_failed(step, message)
                    return "fail"
                self.hooks.step_retry(step, attempt, message)
                attempt += 1
                self.control.sleep(policy.delay_seconds())
        self.hooks.step_failed(step, "Step failed")
        return "fail"


def _wait_seconds(step: WorkflowStep, resolved: str) -> float:
    text = (resolved or step.value or "").strip()
    if text:
        try:
            return max(0.0, float(text))
        except ValueError:
            pass
    return max(0.0, step.timeout_ms / 1000)
