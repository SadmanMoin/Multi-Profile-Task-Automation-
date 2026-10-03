"""Ask the user to finish a human check. Nothing here solves it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.models.execution import ManualAction
from app.services.errors import ServiceError
from app.services.execution_service import ExecutionService
from app.ui.widgets import show_error


class ManualActionDialog(QDialog):
    def __init__(self, action: ManualAction, execution: ExecutionService, parent=None) -> None:
        super().__init__(parent)
        self.action = action
        self.execution = execution
        self.setWindowTitle("Manual action required")
        self.resize(520, 460)
        self.setModal(False)
        text = QLabel(
            f"Profile: {action.profile_name}\n"
            f"Workflow: {action.workflow_name}\n"
            f"Step: {action.step_number}\n\n"
            f"Reason:\n{action.reason}\n\n"
            "Complete the verification in the browser, then press Resume. "
            "This application will not solve it."
        )
        text.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        if action.screenshot_path and Path(action.screenshot_path).is_file():
            image = QLabel()
            pixmap = QPixmap(action.screenshot_path)
            image.setPixmap(pixmap.scaledToWidth(480))
            layout.addWidget(image)
        open_browser = QPushButton("Open Browser")
        resume = QPushButton("Resume")
        resume.setObjectName("primary")
        stop = QPushButton("Stop")
        stop.setObjectName("danger")
        open_browser.clicked.connect(self._focus)
        resume.clicked.connect(self._resume)
        stop.clicked.connect(self._stop)
        row = QHBoxLayout()
        row.addWidget(open_browser)
        row.addWidget(resume)
        row.addWidget(stop)
        layout.addLayout(row)

    def _focus(self) -> None:
        try:
            self.execution.focus(self.action.task_run_id)
        except ServiceError as exc:
            show_error(self, exc)

    def _resume(self) -> None:
        self.execution.resume(self.action.task_run_id)
        self.accept()

    def _stop(self) -> None:
        self.execution.stop(self.action.task_run_id)
        self.accept()
