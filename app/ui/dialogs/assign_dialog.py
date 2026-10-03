"""Choose which profiles a workflow is allowed to run on. This does not start a run."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from app.services.profile_service import list_profiles


class AssignDialog(QDialog):
    def __init__(self, workflow_name: str, selected_ids: list[int], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign workflow")
        self.resize(420, 360)
        self._boxes: list[tuple[int, QCheckBox]] = []
        layout = QVBoxLayout(self)
        note = QLabel(f"{workflow_name}\n\nAssignment does not run the workflow. Press Run when you are ready.")
        note.setWordWrap(True)
        layout.addWidget(note)
        for profile in list_profiles():
            if profile.id is None:
                continue
            box = QCheckBox(profile.name + ("" if profile.enabled else " (disabled)"))
            box.setChecked(profile.id in selected_ids)
            box.setEnabled(profile.enabled)
            self._boxes.append((profile.id, box))
            layout.addWidget(box)
        layout.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_ids(self) -> list[int]:
        return [profile_id for profile_id, box in self._boxes if box.isChecked()]
