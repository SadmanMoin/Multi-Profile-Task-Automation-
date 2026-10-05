"""Adjust paths when the app is running from the packaged executable."""

from __future__ import annotations

import sys
from pathlib import Path


def prepare_packaged_runtime() -> None:
    """Point Playwright at the driver shipped beside the frozen app."""
    if not getattr(sys, "frozen", False):
        return
    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    node = base / "playwright" / "driver" / "node.exe"
    cli = base / "playwright" / "driver" / "package" / "cli.js"
    if not node.is_file() or not cli.is_file():
        return
    import playwright._impl._driver as driver_module

    driver_module.compute_driver_executable = lambda: (str(node), str(cli))
