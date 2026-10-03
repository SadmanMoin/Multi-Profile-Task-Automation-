"""Health-check profiles, then queue an explicit run."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.automation.health_checker import health_ok, health_summary, run_health_checks
from app.models.workflow import Workflow
from app.services.profile_service import get_profile, list_profiles
from app.services.settings_service import get_int


class RunDialog(QDialog):
    def __init__(self, workflow: Workflow, selected_ids: list[int], parent=None) -> None:
        super().__init__(parent)
        self.workflow = workflow
        self.setWindowTitle("Run workflow")
        self.resize(480, 420)
        self._boxes: list[tuple[int, QCheckBox]] = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Workflow: {workflow.name} v{workflow.version}"))
        for profile in list_profiles():
            if profile.id is None or not profile.enabled:
                continue
            box = QCheckBox(profile.name)
            box.setChecked(profile.id in selected_ids)
            self._boxes.append((profile.id, box))
            layout.addWidget(box)
        self.dry_run = QCheckBox("Dry run (find targets, do not click, type, or submit)")
        layout.addWidget(self.dry_run)
        check = QDialogButtonBox()
        health = check.addButton("Health check", QDialogButtonBox.ButtonRole.ActionRole)
        health.clicked.connect(self._show_health)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Run")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(check)
        layout.addWidget(buttons)

    def selected_ids(self) -> list[int]:
        return [profile_id for profile_id, box in self._boxes if box.isChecked()]

    def _profiles(self):
        return [get_profile(profile_id) for profile_id in self.selected_ids()]

    def _results(self):
        minimum = get_int("min_free_disk_mb")
        output = []
        for profile in self._profiles():
            checks = run_health_checks(profile, self.workflow, min_free_mb=minimum)
            output.append((profile, checks))
        return output

    def _show_health(self) -> None:
        if not self.selected_ids():
            QMessageBox.warning(self, "Health check", "Select at least one profile.")
            return
        blocks = []
        for profile, checks in self._results():
            blocks.append(f"{profile.name}\n{health_summary(checks)}")
        box = QMessageBox(self)
        box.setWindowTitle("Health check")
        box.setText("Review the checks below. Warnings do not block a run. Failures do.")
        box.setDetailedText("\n\n".join(blocks))
        box.exec()

    def _accept(self) -> None:
        if not self.selected_ids():
            QMessageBox.warning(self, "Run", "Select at least one profile.")
            return
        failures = []
        warnings = []
        for profile, checks in self._results():
            if not health_ok(checks):
                failures.append(f"{profile.name}\n{health_summary(checks)}")
            elif any(item.warning for item in checks):
                warnings.append(f"{profile.name}\n{health_summary(checks)}")
        if failures:
            QMessageBox.critical(self, "Health check", "Fix these checks before running:\n\n" + "\n\n".join(failures))
            return
        if warnings:
            answer = QMessageBox.question(
                self,
                "Health check",
                "There are warnings:\n\n" + "\n\n".join(warnings) + "\n\nRun anyway?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.accept()
