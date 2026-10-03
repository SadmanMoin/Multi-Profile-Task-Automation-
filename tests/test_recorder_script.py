"""The recorder source has to install itself on the next page."""

from app.automation.recorder import RECORDER_SCRIPT


def test_recorder_script_invokes_itself():
    source = RECORDER_SCRIPT.strip()
    assert source.startswith("(() =>")
    assert source.endswith("})();")


def test_recorder_script_listens_for_typing_on_document():
    assert 'addEventListener("input"' in RECORDER_SCRIPT
    assert 'addEventListener("click"' in RECORDER_SCRIPT
