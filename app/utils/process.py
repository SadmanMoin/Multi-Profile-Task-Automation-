"""Process checks used for profile locks and crash cleanup.

Only Chrome processes this app recorded are eligible to be closed.
User browser data is never deleted.
"""

from __future__ import annotations

import subprocess
import sys

from app.utils.logger import get_logger


logger = get_logger("process")


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if sys.platform != "win32":
        try:
            import os

            os.kill(int(pid), 0)
        except OSError:
            return False
        return True
    return _windows_pid_alive(int(pid))


def process_image_name(pid: int) -> str:
    if pid <= 0 or sys.platform != "win32":
        return ""
    return _windows_image_name(int(pid))


def process_command_line(pid: int) -> str:
    if pid <= 0 or sys.platform != "win32":
        return ""
    script = (
        "(Get-CimInstance Win32_Process -Filter "
        f"'ProcessId = {int(pid)}').CommandLine"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not read command line for pid %s: %s", pid, exc)
        return ""
    return result.stdout or ""


def find_chrome_pid(user_data_dir: str) -> int | None:
    """Find the browser process Playwright launched for this user-data directory."""
    if sys.platform != "win32" or not user_data_dir:
        return None
    needle = user_data_dir.replace("'", "''").lower()
    script = f"""
$rows = Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'"
foreach ($row in $rows) {{
  $cmd = $row.CommandLine
  if (-not $cmd) {{ continue }}
  $lower = $cmd.ToLower()
  if ($lower.Contains('{needle}') -and ($lower -notlike '*--type=*')) {{
    Write-Output $row.ProcessId
    break
  }}
}}
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Could not find Chrome pid: %s", exc)
        return None
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None


def terminate_automation_chrome(pid: int | None, user_data_dir: str) -> bool:
    """Close an orphaned automation Chrome process.

    Returns False when the pid is not a Chrome process for this profile.
    This never deletes profile data.
    """
    if not pid or pid <= 0:
        return False
    image = process_image_name(int(pid)).lower()
    if "chrome.exe" not in image and "chromium" not in image:
        logger.info("Refusing to terminate pid %s because it is not Chrome", pid)
        return False
    command = process_command_line(int(pid)).lower()
    needle = (user_data_dir or "").lower()
    if needle and needle not in command:
        logger.warning(
            "Refusing to terminate pid %s because its command line does not match the profile",
            pid,
        )
        return False
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("taskkill failed for pid %s: %s", pid, exc)
        return False
    if result.returncode != 0:
        logger.warning("taskkill returned %s for pid %s", result.returncode, pid)
        return False
    logger.info("Closed orphaned automation Chrome pid %s", pid)
    return True


def _windows_pid_alive(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    process_query = 0x1000
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetLastError.restype = wintypes.DWORD
    handle = kernel32.OpenProcess(process_query, False, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    error = kernel32.GetLastError()
    access_denied = 5
    return error == access_denied


def _windows_image_name(pid: int) -> str:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    process_query = 0x1000
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(process_query, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)
