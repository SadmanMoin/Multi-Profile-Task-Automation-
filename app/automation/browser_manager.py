"""Launch the user's installed Chrome with one profile.

Automation stays visible. This does not change the browser fingerprint,
rotate proxies, or remove Chrome's automation flags.

Chrome 136+ refuses DevTools on the default User Data folder. Learn Mode uses
a private copy under data/chrome-profiles and never deletes the daily Chrome
folder.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from app.automation.errors import AutomationError, ProfileInUse
from app.models.profile import Profile
from app.utils.logger import get_logger
from app.utils.paths import get_data_dir
from app.utils.process import find_chrome_pid


logger = get_logger("browser")

# Drop Playwright flags that hide extensions, sync, and the New Tab page.
# Keep --user-data-dir and --remote-debugging-pipe so Learn Mode can record.
PLAYWRIGHT_ARGS_TO_DROP = [
    "--disable-extensions",
    "--disable-sync",
    "--no-sandbox",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-component-extensions-with-background-pages",
    "--metrics-recording-only",
    "--disable-search-engine-choice-screen",
    "--disable-infobars",
]


def launch_error(exc: BaseException) -> Exception:
    message = str(exc)
    lowered = message.lower()
    if "non-default data directory" in lowered:
        return AutomationError(
            "Chrome blocked control of the default User Data folder. "
            "Close every Chrome window, including background Chrome, and try again."
        )
    if (
        "processsingleton" in lowered
        or "already in use" in lowered
        or "opening in existing browser session" in lowered
    ):
        return ProfileInUse(
            "Your real Chrome profile is already open. "
            "Close every Chrome window (check the tray), then enter Learn Mode again."
        )
    if "timeout" in lowered:
        return AutomationError(
            "Chrome opened but Learn Mode could not connect. "
            "Close every Chrome window (check the tray), then enter Learn Mode again."
        )
    first_line = message.strip().splitlines()[0] if message.strip() else "Chrome failed to start."
    return AutomationError(first_line[:300])


def default_chrome_user_data() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"


def is_system_chrome_user_data(path: str | Path) -> bool:
    try:
        return Path(path).expanduser().resolve() == default_chrome_user_data().resolve()
    except OSError:
        return False


SEED_MARKER = ".seeded-v3"
_SKIP_DIR_NAMES = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "ShaderCache",
    "GrShaderCache",
    "Service Worker",
    "Crashpad",
    "BrowserMetrics",
    "optimization_guide_hint_cache_store",
}
_SKIP_FILE_NAMES = {
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "lockfile",
}


def isolated_user_data_dir(profile: Profile) -> Path:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", profile.name).strip("_") or "profile"
    parent = get_data_dir() / "chrome-profiles"
    parent.mkdir(parents=True, exist_ok=True)
    return parent / f"{profile.id or 0}-{slug}"


def resolve_launch_dirs(profile: Profile) -> tuple[Path, str]:
    """Chrome blocks remote debugging on the default User Data folder.

    Copy the selected profile into data/chrome-profiles. Never write into or
    delete the daily Chrome User Data folder.
    """
    source = Path(profile.user_data_dir)
    directory = profile.chrome_profile_directory.strip() or "Default"
    if not is_system_chrome_user_data(source):
        return source, directory
    dest = isolated_user_data_dir(profile)
    _seed_isolated_profile(source, directory, dest)
    return dest, directory


def _points_at_real_chrome(path: Path) -> bool:
    try:
        resolved = path.resolve()
        real = default_chrome_user_data().resolve()
        return resolved == real or real in resolved.parents
    except OSError:
        return False


def _seed_isolated_profile(source_user_data: Path, source_directory: str, dest: Path) -> None:
    if dest.is_junction() or dest.is_symlink():
        logger.warning("Removing Chrome junction at %s so the real profile is not written to", dest)
        dest.unlink()
    marker = dest / SEED_MARKER
    if marker.is_file() and (dest / source_directory).exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    src = source_user_data / source_directory
    target = dest / source_directory
    if src.is_dir():
        _copy_tree_skipping_locks(src, target)
        _mark_clean_exit(target)
        logger.info("Copied Chrome profile %s into the isolated automation folder", source_directory)
    else:
        logger.warning("Chrome profile folder missing at %s; Learn Mode will use a fresh profile", src)
    _write_isolated_local_state(source_user_data, dest, source_directory)
    first_run = source_user_data / "First Run"
    if first_run.is_file():
        _copy_file_best_effort(first_run, dest / "First Run")
    else:
        (dest / "First Run").write_text("", encoding="utf-8")
    avatars = source_user_data / "Avatars"
    if avatars.is_dir():
        _copy_tree_skipping_locks(avatars, dest / "Avatars")
    marker.write_text(f"{src}\n{source_directory}", encoding="utf-8")


def _copy_tree_skipping_locks(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        dirs[:] = [name for name in dirs if name not in _SKIP_DIR_NAMES]
        relative = Path(root).relative_to(src)
        target_dir = dest / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            if name in _SKIP_FILE_NAMES:
                continue
            _copy_file_best_effort(Path(root) / name, target_dir / name)


def _copy_file_best_effort(src: Path, dest: Path) -> None:
    try:
        shutil.copy2(src, dest)
    except OSError:
        logger.debug("Skipped locked or unreadable Chrome file %s", src)


def _mark_clean_exit(profile_dir: Path) -> None:
    prefs_path = profile_dir / "Preferences"
    if not prefs_path.is_file():
        return
    try:
        prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    profile = prefs.setdefault("profile", {})
    profile["exit_type"] = "Normal"
    profile["exited_cleanly"] = True
    try:
        prefs_path.write_text(json.dumps(prefs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except OSError:
        logger.debug("Could not mark Chrome profile %s as a clean exit", profile_dir)


def _write_isolated_local_state(source_user_data: Path, dest: Path, directory: str) -> None:
    data: dict = {}
    src_state = source_user_data / "Local State"
    if src_state.is_file():
        try:
            data = json.loads(src_state.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not read Chrome Local State; building a minimal copy")
            data = {}
    profile = data.setdefault("profile", {})
    cache = profile.get("info_cache") if isinstance(profile.get("info_cache"), dict) else {}
    selected = cache.get(directory)
    if not isinstance(selected, dict):
        selected = {"name": directory}
    profile["info_cache"] = {directory: selected}
    profile["last_used"] = directory
    profile["last_active_profiles"] = [directory]
    profile["profiles_order"] = [directory]
    profile["picker_shown"] = True
    browser = data.setdefault("browser", {})
    browser["show_picker_on_startup"] = False
    browser["first_run_finished"] = True
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "Local State").write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _remove_launch_dir(path: Path) -> None:
    if path.is_junction() or path.is_symlink():
        path.unlink()
        return
    if _points_at_real_chrome(path):
        raise AutomationError("Refusing to delete the real Chrome profile")
    try:
        if path.is_dir():
            shutil.rmtree(path)
            return
        if path.exists():
            path.unlink()
    except OSError as exc:
        raise AutomationError(
            f"Could not replace the old automation Chrome folder at {path}: {exc}"
        ) from exc


class BrowserManager:
    def __init__(self) -> None:
        self._playwright = None
        self._context = None
        self._launch_user_data = ""

    @property
    def context(self):
        return self._context

    def launch(self, profile: Profile):
        executable = Path(profile.chrome_executable_path)
        source = Path(profile.user_data_dir)
        if not executable.is_file():
            raise AutomationError(f"Chrome executable not found: {executable}")
        if not source.is_dir():
            raise AutomationError(f"Profile path not found: {source}")
        try:
            from app.utils.frozen import prepare_packaged_runtime

            prepare_packaged_runtime()
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise AutomationError(
                "Playwright is not installed. Run: pip install playwright"
            ) from exc

        user_data, directory = resolve_launch_dirs(profile)
        self._launch_user_data = str(user_data)
        logger.info(
            "Launching Chrome profile %s (%s) user_data=%s",
            profile.name,
            directory,
            user_data,
        )
        self._playwright = sync_playwright().start()
        try:
            # Chromium sandbox stays on so Chrome does not show the --no-sandbox bar.
            # Playwright still gets --user-data-dir and --remote-debugging-pipe.
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data),
                executable_path=str(executable),
                headless=False,
                no_viewport=True,
                timeout=60000,
                chromium_sandbox=True,
                ignore_default_args=PLAYWRIGHT_ARGS_TO_DROP,
                args=[
                    f"--profile-directory={directory}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-profile-picker",
                    "--hide-crash-restore-bubble",
                ],
            )
        except Exception as exc:
            self.close()
            raise launch_error(exc) from exc
        return self._context

    def find_pid(self, profile: Profile) -> int | None:
        return find_chrome_pid(self._launch_user_data or profile.user_data_dir)

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
