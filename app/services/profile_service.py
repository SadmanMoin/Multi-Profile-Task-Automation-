"""Create and inspect local Chrome profile records.

The service never creates website accounts and never deletes Chrome user data.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from app.automation.browser_manager import BrowserManager
from app.automation.errors import ProfileInUse
from app.automation.secrets import is_secret_variable, normalize_variable_name
from app.database import repositories
from app.models.profile import Profile, ProfileVariable
from app.services.errors import ServiceError
from app.utils.constants import LockKind
from app.utils.crypto import decrypt_text, encrypt_text
from app.utils.logger import get_logger
from app.utils.process import pid_alive


logger = get_logger("profiles")


def status_label(profile: Profile) -> str:
    if not profile.enabled:
        return "DISABLED"
    if profile.lock_owner_pid and pid_alive(profile.lock_owner_pid):
        return "IN_USE"
    return "IDLE"


def default_chrome_path() -> str:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return str(candidates[0])


def default_user_data_dir() -> str:
    return str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data")


def discover_chrome_profiles(user_data_dir: str) -> list[tuple[str, str]]:
    """Return (directory, display name) from Chrome's local profile list."""
    path = Path(user_data_dir) / "Local State"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cache = data.get("profile", {}).get("info_cache", {})
    except (OSError, json.JSONDecodeError, AttributeError):
        return []
    found: list[tuple[str, str]] = []
    if not isinstance(cache, dict):
        return []
    for directory, info in cache.items():
        display = ""
        if isinstance(info, dict):
            display = str(info.get("name") or "")
        found.append((str(directory), display))
    return sorted(found, key=lambda item: item[0].lower())


def list_profiles() -> list[Profile]:
    return repositories.list_profiles()


def get_profile(profile_id: int) -> Profile:
    profile = repositories.get_profile(profile_id)
    if profile is None:
        raise ServiceError("Profile not found")
    return profile


def _validate(profile: Profile, ignore_id: int | None = None) -> None:
    if not profile.name.strip():
        raise ServiceError("Profile name is required")
    if not profile.chrome_executable_path.strip():
        raise ServiceError("Chrome executable path is required")
    if not profile.user_data_dir.strip():
        raise ServiceError("Chrome user data path is required")
    if not profile.chrome_profile_directory.strip():
        raise ServiceError("Chrome profile name is required")
    if repositories.profile_name_exists(profile.name.strip(), ignore_id=ignore_id):
        raise ServiceError("A profile with that name already exists")


def create_profile(profile: Profile) -> Profile:
    _validate(profile)
    created = repositories.create_profile(profile)
    logger.info("Created profile %s", created.name)
    return created


def update_profile(profile: Profile) -> Profile:
    if profile.id is None:
        raise ServiceError("Profile not found")
    _validate(profile, ignore_id=profile.id)
    updated = repositories.update_profile(profile)
    logger.info("Updated profile %s", updated.name)
    return updated


def set_enabled(profile_id: int, enabled: bool) -> None:
    profile = get_profile(profile_id)
    if not enabled and status_label(profile) == "IN_USE":
        raise ServiceError("Profile currently in use")
    repositories.set_profile_enabled(profile_id, enabled)


def delete_profile(profile_id: int) -> None:
    profile = get_profile(profile_id)
    if status_label(profile) == "IN_USE":
        raise ServiceError("Profile currently in use")
    repositories.delete_profile(profile_id)
    logger.info("Deleted profile record %s", profile.name)


def test_profile(profile_id: int) -> str:
    profile = get_profile(profile_id)
    if not profile.enabled:
        raise ServiceError("Profile is disabled")
    if not repositories.acquire_lock(profile_id, owner_pid=os.getpid(), run_id=None, kind=LockKind.TEST):
        raise ServiceError("Profile currently in use")
    browser = BrowserManager()
    try:
        context = browser.launch(profile)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("about:blank", timeout=15000, wait_until="domcontentloaded")
        title = page.title()
        logger.info("Profile test succeeded for %s", profile.name)
        return f"Launched successfully. Page title: {title or 'about:blank'}"
    except ProfileInUse as exc:
        raise ServiceError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Profile test failed for %s", profile.name)
        raise ServiceError(str(exc)) from exc
    finally:
        browser.close()
        repositories.release_lock(profile_id, kind=LockKind.TEST)


def launch_profile(profile_id: int) -> None:
    """Open Chrome for the user. This is not an automation run and is not locked."""
    profile = get_profile(profile_id)
    executable = Path(profile.chrome_executable_path)
    user_data = Path(profile.user_data_dir)
    if not executable.is_file():
        raise ServiceError(f"Chrome executable not found: {executable}")
    if not user_data.is_dir():
        raise ServiceError(f"Profile path not found: {user_data}")
    command = [
        str(executable),
        f"--user-data-dir={user_data}",
        f"--profile-directory={profile.chrome_profile_directory}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    subprocess.Popen(command, **kwargs)
    logger.info("Opened Chrome for profile %s", profile.name)


def list_variables(profile_id: int) -> list[ProfileVariable]:
    get_profile(profile_id)
    return repositories.list_profile_variables(profile_id)


def save_variable(profile_id: int, name: str, value: str | None, is_secret: bool | None = None) -> None:
    get_profile(profile_id)
    normalized = normalize_variable_name(name)
    if not normalized:
        raise ServiceError("Variable name is required")
    secret = is_secret_variable(normalized) if is_secret is None else bool(is_secret)
    existing = repositories.get_profile_variable_secret(profile_id, normalized)
    if value is None or value == "":
        if existing is None:
            raise ServiceError("Variable value is required")
        encrypted = existing[0]
        if is_secret is None:
            secret = existing[1]
    else:
        encrypted = encrypt_text(value)
    repositories.upsert_profile_variable(profile_id, normalized, encrypted, secret)
    logger.info("Saved profile variable %s secret=%s", normalized, secret)


def delete_variable(variable_id: int) -> None:
    repositories.delete_profile_variable(variable_id)


def load_variable_values(profile_id: int) -> dict[str, str]:
    """Decrypt values for the replay engine. Do not log the result."""
    values: dict[str, str] = {}
    for name, encrypted, _is_secret in repositories.list_profile_variable_secrets(profile_id):
        if not encrypted:
            continue
        try:
            values[name] = decrypt_text(encrypted)
        except ValueError:
            logger.error("Could not decrypt profile variable %s", name)
    return values


def reveal_variable(profile_id: int, name: str) -> str:
    """Return a non-secret value for editing. Secret values are not revealed."""
    normalized = normalize_variable_name(name)
    stored = repositories.get_profile_variable_secret(profile_id, normalized)
    if stored is None:
        return ""
    encrypted, is_secret = stored
    if is_secret:
        return ""
    if not encrypted:
        return ""
    return decrypt_text(encrypted)
