"""Launch the user's installed Chrome with one profile.

Automation stays visible. This does not change the browser fingerprint,
rotate proxies, or remove Chrome's automation flags.
"""

from __future__ import annotations

from pathlib import Path

from app.automation.errors import AutomationError, ProfileInUse
from app.models.profile import Profile
from app.utils.logger import get_logger
from app.utils.process import find_chrome_pid


logger = get_logger("browser")


class BrowserManager:
    def __init__(self) -> None:
        self._playwright = None
        self._context = None

    @property
    def context(self):
        return self._context

    def launch(self, profile: Profile):
        executable = Path(profile.chrome_executable_path)
        user_data = Path(profile.user_data_dir)
        if not executable.is_file():
            raise AutomationError(f"Chrome executable not found: {executable}")
        if not user_data.is_dir():
            raise AutomationError(f"Profile path not found: {user_data}")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise AutomationError(
                "Playwright is not installed. Run: pip install playwright"
            ) from exc

        directory = profile.chrome_profile_directory.strip() or "Default"
        logger.info("Launching Chrome profile %s (%s)", profile.name, directory)
        self._playwright = sync_playwright().start()
        try:
            # no_viewport keeps the normal window size so Learn Mode matches daily use.
            # Automation flags are left in place on purpose.
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data),
                executable_path=str(executable),
                headless=False,
                no_viewport=True,
                args=[
                    f"--profile-directory={directory}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
        except Exception as exc:
            self.close()
            message = str(exc)
            lowered = message.lower()
            if (
                "processsingleton" in lowered
                or "already in use" in lowered
                or "target closed" in lowered
                or "opening in existing browser session" in lowered
            ):
                raise ProfileInUse(
                    "Profile currently in use. Close Chrome for this profile and try again."
                ) from exc
            raise AutomationError(message) from exc
        return self._context

    def find_pid(self, profile: Profile) -> int | None:
        return find_chrome_pid(profile.user_data_dir)

    def close(self) -> None:
        context = self._context
        playwright = self._playwright
        self._context = None
        self._playwright = None
        if context is not None:
            try:
                context.close()
            except Exception:
                logger.exception("Failed to close the browser context")
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                logger.exception("Failed to stop Playwright")
