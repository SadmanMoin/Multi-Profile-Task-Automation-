"""Order element locators from most stable to least stable."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.workflow import ElementTarget


@dataclass(frozen=True)
class LocatorPlan:
    kind: str
    role: str = ""
    name: str = ""
    value: str = ""
    x: float | None = None
    y: float | None = None


def css_escape(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else f"\\{character}" for character in value)


def attr_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def locator_plan(target: ElementTarget) -> list[LocatorPlan]:
    """Prefer role and accessible name. Coordinates are the final fallback."""
    plans: list[LocatorPlan] = []
    accessible = target.name or target.text
    if target.role and accessible and target.role.lower() not in {"generic", "none"}:
        plans.append(LocatorPlan("role", role=target.role, name=accessible))
    if target.label:
        plans.append(LocatorPlan("label", value=target.label))
    if target.placeholder:
        plans.append(LocatorPlan("placeholder", value=target.placeholder))
    test_id = target.test_id or target.attributes.get("data-testid", "")
    if test_id:
        plans.append(LocatorPlan("testid", value=test_id))
    element_id = target.attributes.get("id", "")
    if element_id:
        plans.append(LocatorPlan("css", value=f"#{css_escape(element_id)}"))
    attr_name = target.attributes.get("name", "")
    if attr_name and target.tag:
        plans.append(LocatorPlan("css", value=f'{target.tag}[name="{attr_escape(attr_name)}"]'))
    if target.text and not (target.role and accessible):
        plans.append(LocatorPlan("text", value=target.text))
    elif target.name and not target.role:
        plans.append(LocatorPlan("text", value=target.name))
    if target.selector:
        plans.append(LocatorPlan("css", value=target.selector))
    if target.fallback_selector:
        plans.append(LocatorPlan("xpath", value=target.fallback_selector))
    if target.x is not None and target.y is not None:
        plans.append(LocatorPlan("coordinate", x=target.x, y=target.y))
    return plans
