"""Workflow, step, and element-target models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.utils.constants import ACTION_TYPES, ActionType, VerificationType


class ElementTarget(BaseModel):
    """How a recorded element can be found again.

    Replay tries role and name first. Coordinates are only a last resort.
    """

    role: str = ""
    name: str = ""
    text: str = ""
    tag: str = ""
    label: str = ""
    placeholder: str = ""
    input_type: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    selector: str = ""
    fallback_selector: str = ""
    test_id: str = ""
    x: float | None = None
    y: float | None = None


class WorkflowStep(BaseModel):
    id: int | None = None
    workflow_id: int | None = None
    step_number: int = 1
    action_type: str = ActionType.WAIT
    target: ElementTarget = Field(default_factory=ElementTarget)
    value: str = ""
    wait_before_ms: int = 0
    wait_after_ms: int = 0
    timeout_ms: int = 15000
    verification_type: str = VerificationType.NONE
    verification_expected: str = ""
    retry_count: int = 2
    retry_delay_ms: int = 3000
    skip_if_already_complete: bool = False

    @field_validator("action_type")
    @classmethod
    def _known_action(cls, value: str) -> str:
        if value not in ACTION_TYPES:
            raise ValueError(f"Unsupported action type: {value}")
        return value


class WorkflowVariable(BaseModel):
    id: int | None = None
    workflow_id: int
    name: str
    is_secret: bool = False
    description: str = ""


class Workflow(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)
    variables: list[WorkflowVariable] = Field(default_factory=list)


def target_label(target: ElementTarget) -> str:
    return (
        target.name
        or target.label
        or target.text
        or target.placeholder
        or target.selector
        or "element"
    )


def display_typed_value(step: WorkflowStep) -> str:
    """Value safe to show in the review list."""
    if step.action_type != ActionType.TYPE:
        return step.value
    sensitive_type = (step.target.input_type or step.target.attributes.get("type") or "").lower()
    if sensitive_type == "password" and "{{" not in (step.value or ""):
        return "***"
    return step.value


def step_summary(step: WorkflowStep) -> str:
    action = step.action_type
    label = target_label(step.target)
    if action == ActionType.OPEN_URL:
        return f"Open {step.value or 'website'}"
    if action == ActionType.CLICK:
        return f'Click "{label}"'
    if action == ActionType.TYPE:
        return f'Type "{display_typed_value(step)}" into "{label}"'
    if action == ActionType.PRESS_KEY:
        return f"Press {step.value or 'key'}"
    if action == ActionType.NAVIGATE_BACK:
        return "Go back"
    if action == ActionType.NAVIGATE_FORWARD:
        return "Go forward"
    if action == ActionType.RELOAD:
        return "Reload page"
    if action == ActionType.WAIT:
        seconds = step.value.strip() if step.value.strip() else f"{step.timeout_ms / 1000:g}s"
        return f"Wait {seconds}"
    if action == ActionType.VERIFY:
        expected = f' "{step.verification_expected}"' if step.verification_expected else ""
        kind = step.verification_type or "condition"
        return f"Verify {kind}{expected}"
    return action


def diff_workflows(left: Workflow, right: Workflow) -> str:
    lines: list[str] = []
    if left.name != right.name:
        lines.append(f"Name: {left.name}  →  {right.name}")
    count = max(len(left.steps), len(right.steps))
    for index in range(count):
        before = step_summary(left.steps[index]) if index < len(left.steps) else "(none)"
        after = step_summary(right.steps[index]) if index < len(right.steps) else "(none)"
        if before != after:
            lines.append(f"Step {index + 1}: {before}  →  {after}")
    if not lines:
        return "No differences."
    return "\n".join(lines)
