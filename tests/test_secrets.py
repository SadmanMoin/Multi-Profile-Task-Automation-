from app.automation.secrets import find_variables, resolve_template, sanitize_type_value, sensitive_kind
from app.models.workflow import ElementTarget
import logging

from app.utils.logger import RedactFilter
from app.utils.redact import redact_text


def test_password_value_becomes_a_placeholder():
    target = ElementTarget(tag="input", input_type="password", attributes={"type": "password"})
    assert sensitive_kind(target) == "PASSWORD"
    stored = sanitize_type_value(target, "super-secret-value", sensitive=True, placeholder="{{PASSWORD}}")
    assert stored == "{{PASSWORD}}"
    assert "super-secret" not in stored


def test_seed_phrase_field_is_not_kept():
    target = ElementTarget(label="Seed phrase", tag="textarea")
    stored = sanitize_type_value(target, "alpha beta gamma delta", sensitive=True)
    assert stored == "{{SEED_PHRASE}}"
    assert "alpha" not in stored


def test_resolve_and_redact():
    assert find_variables("{{username}} and {{ API_KEY }}") == ["USERNAME", "API_KEY"]
    resolved = resolve_template("Hello {{USERNAME}}", {"USERNAME": "ada"})
    assert resolved == "Hello ada"
    assert redact_text("password=hunter2 token: abc") == "password=*** token: ***"


def test_log_filter_redacts_secrets():
    record = logging.LogRecord("bta", logging.INFO, __file__, 1, "password=%s", ("hunter2",), None)
    assert RedactFilter().filter(record)
    assert "hunter2" not in record.getMessage()
    assert "***" in record.getMessage()
