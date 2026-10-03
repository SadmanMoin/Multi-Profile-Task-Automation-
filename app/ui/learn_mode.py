"""Record a workflow by watching one Chrome profile."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.automation.errors import AutomationError, ProfileInUse
from app.automation.recorder import LearnSession
from app.automation.secrets import find_variables
from app.models.workflow import Workflow
from app.services.errors import ServiceError
from app.services.profile_service import list_profiles
from app.services.workflow_service import save_workflow
from app.ui.step_editor import StepEditor
from app.ui.widgets import page_title, show_error


class LearnPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.session = LearnSession()
        self.workflow_id: int | None = None
        self.name = QLineEdit()
        self.name.setPlaceholderText("Project A Daily Task")
        self.description = QLineEdit()
        self.description.setPlaceholderText("Optional description")
        self.profile = QComboBox()
        self.start_button = QPushButton("Enter Learn Mode")
        self.start_button.setObjectName("primary")
        self.stop_button = QPushButton("End Learn Mode")
        self.stop_button.setEnabled(False)
        self.save_button = QPushButton("Save Workflow")
        self.placeholders = QLabel("Placeholders: none")
        self.placeholders.setObjectName("hint")
        self.editor = StepEditor()
        self.start_button.clicked.connect(self._start)
        self.stop_button.clicked.connect(self._stop)
        self.save_button.clicked.connect(self._save)
        row = QHBoxLayout()
        row.addWidget(QLabel("Profile"))
        row.addWidget(self.profile, 1)
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        row.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        layout.addWidget(
            page_title(
                "Learn Mode",
                "Perform the task once in Chrome. Clicks, typing, and navigation are recorded. "
                "Passwords and other secrets are stored as {{PLACEHOLDERS}}, never as real values. "
                "Human verification is not solved.",
            )
        )
        layout.addWidget(self.name)
        layout.addWidget(self.description)
        layout.addLayout(row)
        layout.addWidget(self.placeholders)
        layout.addWidget(self.editor, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.refresh()

    def begin_new(self) -> None:
        if self.session.running:
            return
        self.workflow_id = None
        self.name.clear()
        self.description.clear()
        self.editor.set_steps([])
        self.name.setFocus()

    def refresh(self) -> None:
        current = self.profile.currentData()
        self.profile.clear()
        for profile in list_profiles():
            if profile.id is None or not profile.enabled:
                continue
            self.profile.addItem(profile.name, profile.id)
        if current is not None:
            index = self.profile.findData(current)
            if index >= 0:
                self.profile.setCurrentIndex(index)
        if self.session.running and not self.timer.isActive():
            self.timer.start(400)

    def _selected_profile(self):
        profile_id = self.profile.currentData()
        for profile in list_profiles():
            if profile.id == profile_id and profile.enabled:
                return profile
        return None

    def _start(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Learn Mode", "Name the workflow before recording.")
            return
        profile = self._selected_profile()
        if profile is None:
            QMessageBox.warning(self, "Learn Mode", "Add an enabled Chrome profile first.")
            return
        if self.editor.steps and not self._confirm_discard():
            return
        try:
            self.session.start(profile)
        except (ProfileInUse, AutomationError) as exc:
            show_error(self, exc)
            return
        self.workflow_id = None
        self.editor.set_steps([])
        self.editor.set_locked(True)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.timer.start(400)

    def _confirm_discard(self) -> bool:
        answer = QMessageBox.question(self, "Learn Mode", "Discard the steps currently on screen and record again?")
        return answer == QMessageBox.StandardButton.Yes

    def _poll(self) -> None:
        if not self.session.running:
            self.timer.stop()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.editor.set_locked(False)
            if self.session.error:
                QMessageBox.critical(self, "Learn Mode", self.session.error)
                self.session.error = None
            return
        steps = self.session.snapshot()
        if len(steps) != len(self.editor.steps):
            self.editor.set_steps(steps)
            self._show_placeholders()

    def _stop(self) -> None:
        try:
            steps = self.session.stop()
        except AutomationError as exc:
            steps = self.session.snapshot()
            show_error(self, exc)
        self.timer.stop()
        self.editor.set_steps(steps)
        self.editor.set_locked(False)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._show_placeholders()

    def _show_placeholders(self) -> None:
        names = find_variables(*(step.value for step in self.editor.get_steps()))
        self.placeholders.setText("Placeholders: " + (", ".join(names) if names else "none"))

    def _save(self) -> None:
        if self.session.running:
            QMessageBox.warning(self, "Learn Mode", "End Learn Mode before saving.")
            return
        steps = self.editor.get_steps()
        if not steps:
            QMessageBox.warning(self, "Learn Mode", "Record or add at least one step.")
            return
        try:
            saved = save_workflow(
                Workflow(id=self.workflow_id, name=self.name.text(), description=self.description.text()),
                steps,
            )
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.workflow_id = saved.id
        self._show_placeholders()
        QMessageBox.information(
            self,
            "Workflow saved",
            f"Saved {saved.name} v{saved.version}. Assign it to profiles, then press Run. It was not started.",
        )
