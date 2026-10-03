"""Redact secrets before they reach logs, errors, or exports."""

from __future__ import annotations

import re


_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"token|seed(?:\s+phrase)?|private[_-]?key|mnemonic|client[_-]?secret)\b"
    r"(\s*[:=]\s*)(\S+)"
)


def redact_text(text: str | None) -> str:
    if not text:
        return ""
    return _ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}***", str(text))


def redact_known_secrets(text: str | None, secrets: list[str] | tuple[str, ...] | None) -> str:
    cleaned = redact_text(text)
    for secret in secrets or ():
        if secret and len(secret) >= 3:
            cleaned = cleaned.replace(secret, "***")
    return cleaned
