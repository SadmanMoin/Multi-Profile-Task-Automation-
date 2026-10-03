from app.automation.verifier import Observation, assess
from app.utils.constants import VerificationType


def test_page_loaded_and_text_and_url():
    ok, _ = assess(VerificationType.PAGE_LOADED, "", Observation(page_loaded=True))
    assert ok
    failed, message = assess(VerificationType.TEXT_VISIBLE, "Completed", Observation(text_visible=False))
    assert not failed
    assert "Completed" in message
    matched, _ = assess(VerificationType.URL_MATCH, "/done", Observation(url="https://example.test/done"))
    assert matched
    missed, _ = assess(VerificationType.URL_MATCH, "/done", Observation(url="https://example.test/start"))
    assert not missed


def test_element_enabled_requires_visible_and_enabled():
    ok, _ = assess(
        VerificationType.ELEMENT_ENABLED,
        "",
        Observation(element_visible=True, element_enabled=True),
    )
    assert ok
    disabled, message = assess(
        VerificationType.ELEMENT_ENABLED,
        "",
        Observation(element_visible=True, element_enabled=False),
    )
    assert not disabled
    assert "not enabled" in message
