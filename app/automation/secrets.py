"""Placeholders for sensitive fields. Raw secrets are never stored in a workflow."""

from __future__ import annotations

import re

from app.automation.errors import MissingVariable
from app.models.workflow import ElementTarget


EXACT_SECRET_NAMES = {
    "PASSWORD",
    "PASSWD",
    "SECRET",
    "API_KEY",
    "TOKEN",
    "PIN",
    "OTP",
    "SEED_PHRASE",
    "PRIVATE_KEY",
}

_FIELD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"seed|mnemonic|recovery phrase", re.I), "SEED_PHRASE"),
    (re.compile(r"private.?key", re.I), "PRIVATE_KEY"),
    (re.compile(r"api[-_ ]?key|client.?secret", re.I), "API_KEY"),
    (re.compile(r"\bpin\b|one[-_ ]?time|\botp\b", re.I), "PIN"),
    (re.compile(r"\btoken\b", re.I), "TOKEN"),
    (re.compile(r"password|passwd", re.I), "PASSWORD"),
    (re.compile(r"secret", re.I), "SECRET"),
]

VAR_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def normalize_variable_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", (name or "").strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned.upper()


def is_secret_variable(name: str) -> bool:
    upper = normalize_variable_name(name)
    if not upper:
        return False
    if upper in EXACT_SECRET_NAMES:
        return True
    markers = ("PASSWORD", "SECRET", "PRIVATE_KEY", "SEED", "API_KEY", "TOKEN", "MNEMONIC")
    return any(marker in upper for marker in markers)


def sensitive_kind(target: ElementTarget) -> str | None:
    input_type = (target.input_type or target.attributes.get("type") or "").lower()
    autocomplete = (target.attributes.get("autocomplete") or "").lower()
    if input_type == "password" or "password" in autocomplete:
        return "PASSWORD"
    blob = " ".join(
        [
            target.name,
            target.label,
            target.placeholder,
            target.attributes.get("name", ""),
            target.attributes.get("id", ""),
            target.attributes.get("aria-label", ""),
            autocomplete,
        ]
    )
    for pattern, kind in _FIELD_PATTERNS:
        if pattern.search(blob):
            return kind
    return None


def sanitize_type_value(
    target: ElementTarget,
    value: str,
    *,
    sensitive: bool = False,
    placeholder: str = "",
) -> str:
    """Return a placeholder instead of a password, key, seed, or token."""
    kind = sensitive_kind(target)
    if not sensitive and kind is None:
        return value
    if "{{" in (value or ""):
        return value
    if placeholder.startswith("{{") and placeholder.endswith("}}"):
        inner = normalize_variable_name(placeholder[2:-2])
        if inner:
            return "{{" + inner + "}}"
    token = kind or "SECRET"
    return "{{" + token + "}}"


def find_variables(*templates: str) -> list[str]:
    found: list[str] = []
    for template in templates:
        for match in VAR_PATTERN.finditer(template or ""):
            name = normalize_variable_name(match.group(1))
            if name and name not in found:
                found.append(name)
    return found


def resolve_template(template: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = normalize_variable_name(match.group(1))
        if name not in variables:
            raise MissingVariable(name)
        return variables[name]

    return VAR_PATTERN.sub(replace, template or "")
