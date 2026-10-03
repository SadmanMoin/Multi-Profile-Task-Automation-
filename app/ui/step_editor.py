"""Review, reorder, and edit recorded steps."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QPushButton, QVBoxLayout, QWidget

from app.models.workflow import WorkflowStep, step_summary
from app.ui.dialogs.step_dialog import StepDialog
from app.utils.constants import ActionType


class StepEditor(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.steps: list[WorkflowStep] = []
        self.list = QListWidget()
        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.up_button = QPushButton("Up")
        self.down_button = QPushButton("Down")
        self.wait_button = QPushButton("Add wait")
        self.add_button = QPushButton("Add step")
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))
        self.wait_button.clicked.connect(self._add_wait)
        self.add_button.clicked.connect(self._add)
        buttons = QHBoxLayout()
        for button in (
            self.edit_button,
            self.delete_button,
            self.up_button,
            self.down_button,
            self.wait_button,
            self.add_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)
        layout.addLayout(buttons)

    def set_locked(self, locked: bool) -> None:
        for button in (
            self.edit_button,
            self.delete_button,
            self.up_button,
            self.down_button,
            self.wait_button,
            self.add_button,
        ):
            button.setEnabled(not locked)

    def set_steps(self, steps: list[WorkflowStep]) -> None:
        current = self.list.currentRow()
        self.steps = [step.model_copy(deep=True) for step in steps]
        self._refresh()
        if 0 <= current < self.list.count():
            self.list.setCurrentRow(current)

    def get_steps(self) -> list[WorkflowStep]:
        steps = [step.model_copy(deep=True) for step in self.steps]
        for index, step in enumerate(steps, start=1):
            step.step_number = index
        return steps

    def _refresh(self) -> None:
        self.list.clear()
        for index, step in enumerate(self.steps, start=1):
            verify = f"  ·  verify {step.verification_type}" if step.verification_type else ""
            retry = f"  ·  retries {step.retry_count}"
            self.list.addItem(f"{index}. {step_summary(step)}{verify}{retry}")

    def _current(self) -> int:
        return self.list.currentRow()

    def _edit(self) -> None:
        row = self._current()
        if row < 0:
            return
        dialog = StepDialog(self.steps[row], self)
        if dialog.exec() != StepDialog.DialogCode.Accepted:
            return
        self.steps[row] = dialog.to_step(self.steps[row])
        self._refresh()
        self.list.setCurrentRow(row)

    def _delete(self) -> None:
        row = self._current()
        if row < 0:
            return
        del self.steps[row]
        self._refresh()

    def _move(self, delta: int) -> None:
        row = self._current()
        target = row + delta
        if row < 0 or target < 0 or target >= len(self.steps):
            return
        self.steps[row], self.steps[target] = self.steps[target], self.steps[row]
        self._refresh()
        self.list.setCurrentRow(target)

    def _add_wait(self) -> None:
        self.steps.append(WorkflowStep(step_number=len(self.steps) + 1, action_type=ActionType.WAIT, value="1"))
        self._refresh()
        self.list.setCurrentRow(len(self.steps) - 1)

    def _add(self) -> None:
        dialog = StepDialog(parent=self)
        if dialog.exec() != StepDialog.DialogCode.Accepted:
            return
        self.steps.append(dialog.to_step())
        self._refresh()
        self.list.setCurrentRow(len(self.steps) - 1)
