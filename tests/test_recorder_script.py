"""The recorder source has to install itself on the next page."""

from app.automation.recorder import DEFAULT_NEW_TAB_URLS, RECORDER_SCRIPT, normalize_start_url


def test_recorder_script_invokes_itself():
    source = RECORDER_SCRIPT.strip()
    assert source.startswith("(() =>")
    assert source.endswith("})();")


def test_recorder_script_listens_for_typing_on_document():
    assert 'addEventListener("input"' in RECORDER_SCRIPT
    assert 'addEventListener("click"' in RECORDER_SCRIPT


def test_empty_start_url_uses_chrome_new_tab():
    assert normalize_start_url("") == ""
    assert DEFAULT_NEW_TAB_URLS[0] == "chrome://new-tab-page/"


def test_start_url_gains_https_when_scheme_missing():
    assert normalize_start_url("google.com") == "https://google.com"
    assert normalize_start_url("https://google.com") == "https://google.com"
