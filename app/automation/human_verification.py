"""Detect human verification and stop. This module never solves or bypasses it."""

from __future__ import annotations


CHALLENGE_SELECTORS = (
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    'iframe[src*="challenges.cloudflare.com"]',
    'iframe[src*="turnstile"]',
    'iframe[title*="captcha" i]',
    ".g-recaptcha",
    ".h-captcha",
    "#px-captcha",
)

CHALLENGE_PHRASES = (
    "verify you are human",
    "i'm not a robot",
    "i am not a robot",
    "human verification",
    "are you a human",
    "complete the security check",
    "unusual traffic",
    "security verification",
)

MANUAL_REASON = "Human verification detected"


def phrase_matches(text: str | None) -> str | None:
    lowered = (text or "").lower()
    for phrase in CHALLENGE_PHRASES:
        if phrase in lowered:
            return MANUAL_REASON
    return None
