"""In-memory browser used by replay tests. No network and no Chrome."""

from __future__ import annotations

from app.automation.errors import TargetNotFound, VerificationFailed
from app.models.workflow import WorkflowStep


class FakeSession:
    def __init__(self) -> None:
        self.actions: list[tuple] = []
        self.failures_left: dict[int, int] = {}
        self.challenge = False
        self.already_complete = False
        self.fail_verification = False
        self.closed = False
        self.focused = False

    def perform(self, step: WorkflowStep, resolved: str, timeout_s: float) -> None:
        self.actions.append((step.action_type, resolved, step.target.name))
        remaining = self.failures_left.get(step.step_number, 0)
        if remaining:
            self.failures_left[step.step_number] = remaining - 1
            raise TargetNotFound("missing element")

    def verify(self, step: WorkflowStep, timeout_s: float) -> None:
        self.actions.append(("VERIFY", step.verification_type, step.verification_expected))
        if self.already_complete:
            return
        if self.fail_verification:
            raise VerificationFailed("expected state was not found")

    def locate(self, step: WorkflowStep, timeout_s: float) -> bool:
        self.actions.append(("LOCATE", step.target.name))
        return step.target.name != "missing"

    def detect_human_verification(self) -> str | None:
        if self.challenge:
            return "Human verification detected"
        return None

    def screenshot(self, path: str) -> bool:
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"png")
        return True

    def focus(self) -> None:
        self.focused = True

    def close(self) -> None:
        self.closed = True
