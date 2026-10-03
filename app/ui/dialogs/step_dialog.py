"""Edit one workflow step."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.models.workflow import ElementTarget, WorkflowStep
from app.services.settings_service import get_int
from app.utils.constants import ACTION_TYPES, VERIFICATION_TYPES, ActionType


class StepDialog(QDialog):
    def __init__(self, step: WorkflowStep | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit step" if step else "Add step")
        self.resize(560, 520)
        self.action = QComboBox()
        self.action.addItems(list(ACTION_TYPES))
        self.value = QLineEdit()
        self.role = QLineEdit()
        self.accessible_name = QLineEdit()
        self.label = QLineEdit()
        self.placeholder = QLineEdit()
        self.selector = QLineEdit()
        self.fallback = QLineEdit()
        self.test_id = QLineEdit()
        self.wait_before = self._seconds()
        self.wait_after = self._seconds()
        self.timeout = self._seconds(minimum=1, maximum=300, value=get_int("default_timeout_ms") / 1000)
        self.verification = QComboBox()
        self.verification.addItem("None", "")
        for kind in VERIFICATION_TYPES:
            if kind:
                self.verification.addItem(kind, kind)
        self.expected = QLineEdit()
        self.retry_count = QSpinBox()
        self.retry_count.setRange(0, 10)
        self.retry_count.setValue(get_int("default_retry_count"))
        self.retry_delay = self._seconds(maximum=120, value=get_int("default_retry_delay_ms") / 1000)
        self.skip_if_done = QCheckBox("Skip if this verification already passes")
        form = QFormLayout()
        form.addRow("Action", self.action)
        form.addRow("Value / URL", self.value)
        form.addRow("Role", self.role)
        form.addRow("Accessible name", self.accessible_name)
        form.addRow("Label", self.label)
        form.addRow("Placeholder", self.placeholder)
        form.addRow("CSS selector", self.selector)
        form.addRow("XPath fallback", self.fallback)
        form.addRow("Test id", self.test_id)
        form.addRow("Wait before (seconds)", self.wait_before)
        form.addRow("Timeout (seconds)", self.timeout)
        form.addRow("Wait after (seconds)", self.wait_after)
        form.addRow("Verification", self.verification)
        form.addRow("Expected", self.expected)
        form.addRow("Retry count", self.retry_count)
        form.addRow("Retry delay (seconds)", self.retry_delay)
        form.addRow("", self.skip_if_done)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if step is not None:
            self._load(step)

    @staticmethod
    def _seconds(minimum: float = 0, maximum: float = 120, value: float = 0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(0.5)
        spin.setDecimals(1)
        spin.setValue(value)
        return spin

    def _load(self, step: WorkflowStep) -> None:
        index = self.action.findText(step.action_type)
        if index >= 0:
            self.action.setCurrentIndex(index)
        self.value.setText(step.value)
        self.role.setText(step.target.role)
        self.accessible_name.setText(step.target.name)
        self.label.setText(step.target.label)
        self.placeholder.setText(step.target.placeholder)
        self.selector.setText(step.target.selector)
        self.fallback.setText(step.target.fallback_selector)
        self.test_id.setText(step.target.test_id)
        self.wait_before.setValue(step.wait_before_ms / 1000)
        self.wait_after.setValue(step.wait_after_ms / 1000)
        self.timeout.setValue(max(1, step.timeout_ms / 1000))
        verify_index = self.verification.findData(step.verification_type or "")
        if verify_index >= 0:
            self.verification.setCurrentIndex(verify_index)
        self.expected.setText(step.verification_expected)
        self.retry_count.setValue(step.retry_count)
        self.retry_delay.setValue(step.retry_delay_ms / 1000)
        self.skip_if_done.setChecked(step.skip_if_already_complete)

    def to_step(self, existing: WorkflowStep | None = None) -> WorkflowStep:
        target = existing.target.model_copy(deep=True) if existing else ElementTarget()
        target.role = self.role.text().strip()
        target.name = self.accessible_name.text().strip()
        target.label = self.label.text().strip()
        target.placeholder = self.placeholder.text().strip()
        target.selector = self.selector.text().strip()
        target.fallback_selector = self.fallback.text().strip()
        target.test_id = self.test_id.text().strip()
        return WorkflowStep(
            id=None if existing is None else existing.id,
            workflow_id=None if existing is None else existing.workflow_id,
            step_number=1 if existing is None else existing.step_number,
            action_type=self.action.currentText() or ActionType.WAIT,
            target=target,
            value=self.value.text(),
            wait_before_ms=int(self.wait_before.value() * 1000),
            wait_after_ms=int(self.wait_after.value() * 1000),
            timeout_ms=int(self.timeout.value() * 1000),
            verification_type=self.verification.currentData() or "",
            verification_expected=self.expected.text(),
            retry_count=self.retry_count.value(),
            retry_delay_ms=int(self.retry_delay.value() * 1000),
            skip_if_already_complete=self.skip_if_done.isChecked(),
        )
