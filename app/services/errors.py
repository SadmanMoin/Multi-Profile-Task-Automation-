"""Errors that should be shown to the user as-is."""

from __future__ import annotations


class ServiceError(Exception):
    """A user-facing validation or state error."""
