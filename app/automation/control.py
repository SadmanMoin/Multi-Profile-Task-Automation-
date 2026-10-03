"""Pause, resume, and stop signals for one running workflow."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable

from app.automation.errors import StopRequested


class RunControl:
    """Thread-safe control flags.

    The browser thread calls checkpoint() between steps. The interface calls
    pause(), resume(), and stop() from any thread. Focus requests are queued
    and performed on the browser thread, because Playwright is not thread-safe.
    """

    def __init__(self) -> None:
        self._running = threading.Event()
        self._running.set()
        self._stop = threading.Event()
        self._manual = threading.Event()
        self._manual.set()
        self.commands: queue.Queue[str] = queue.Queue()
        self.on_pump: Callable[[], None] | None = None

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()
        self._manual.set()

    def stop(self) -> None:
        self._stop.set()
        self._running.set()
        self._manual.set()

    def request_manual(self) -> None:
        self._manual.clear()

    def request_focus(self) -> None:
        self.commands.put("focus")

    @property
    def stop_requested(self) -> bool:
        return self._stop.is_set()

    def _drain(self) -> None:
        if self.on_pump is not None:
            self.on_pump()

    def checkpoint(self) -> None:
        self._drain()
        if self._stop.is_set():
            raise StopRequested()
        while not self._running.wait(timeout=0.2):
            self._drain()
            if self._stop.is_set():
                raise StopRequested()

    def sleep(self, seconds: float) -> None:
        end = time.monotonic() + max(0.0, seconds)
        while True:
            self.checkpoint()
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            if not self._running.wait(timeout=min(0.2, remaining)):
                continue

    def wait_manual(self) -> None:
        while not self._manual.is_set():
            self._drain()
            if self._stop.is_set():
                raise StopRequested()
            self._manual.wait(timeout=0.2)
        self.checkpoint()
