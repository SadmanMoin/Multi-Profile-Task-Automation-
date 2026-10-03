from app.automation.targeting import locator_plan
from app.models.workflow import ElementTarget


def test_selector_order_prefers_role_and_keeps_coordinates_last():
    target = ElementTarget(
        role="button",
        name="Connect",
        text="Connect",
        tag="button",
        label="Connect",
        placeholder="Search",
        test_id="connect-button",
        attributes={"id": "connect", "name": "connect"},
        selector="#connect",
        fallback_selector="//*[@id='connect']",
        x=12,
        y=40,
    )
    kinds = [plan.kind for plan in locator_plan(target)]
    assert kinds[0] == "role"
    assert kinds[-1] == "coordinate"
    assert kinds.index("role") < kinds.index("label")
    assert kinds.index("label") < kinds.index("placeholder")
    assert kinds.index("testid") < kinds.index("css")
    assert kinds.index("xpath") < kinds.index("coordinate")


def test_coordinate_only_target_has_no_earlier_plan():
    plans = locator_plan(ElementTarget(x=1, y=2))
    assert [plan.kind for plan in plans] == ["coordinate"]
