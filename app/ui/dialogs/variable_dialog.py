"""Profile placeholders such as {{USERNAME}} and {{PASSWORD}}."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from app.services.errors import ServiceError
from app.services.profile_service import delete_variable, list_variables, save_variable
from app.ui.widgets import configure_table, fill_table, selected_id, show_error


class VariableDialog(QDialog):
    def __init__(self, profile_id: int, parent=None) -> None:
        super().__init__(parent)
        self.profile_id = profile_id
        self.setWindowTitle("Profile variables")
        self.resize(560, 420)
        hint = QLabel(
            "Secret values are encrypted on this PC and are never written to workflow logs. "
            "Leave the value blank to keep a saved secret."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        self.table = QTableWidget()
        configure_table(self.table, ["Name", "Secret"])
        self.var_name = QLineEdit()
        self.var_name.setPlaceholderText("PASSWORD")
        self.var_value = QLineEdit()
        self.var_value.setEchoMode(QLineEdit.EchoMode.Password)
        self.var_secret = QCheckBox("Secret")
        self.var_secret.setChecked(True)
        add = QPushButton("Save variable")
        add.setObjectName("primary")
        add.clicked.connect(self._save)
        remove = QPushButton("Delete")
        remove.clicked.connect(self._delete)
        form = QFormLayout()
        form.addRow("Name", self.var_name)
        form.addRow("Value", self.var_value)
        form.addRow("", self.var_secret)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.table)
        layout.addLayout(form)
        layout.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        rows = []
        ids = []
        for variable in list_variables(self.profile_id):
            rows.append([variable.name, "yes" if variable.is_secret else "no"])
            ids.append(variable.id or 0)
        fill_table(self.table, rows, ids)

    def _save(self) -> None:
        try:
            save_variable(
                self.profile_id,
                self.var_name.text(),
                self.var_value.text(),
                is_secret=self.var_secret.isChecked(),
            )
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.var_value.clear()
        self.refresh()

    def _delete(self) -> None:
        variable_id = selected_id(self.table)
        if variable_id is None:
            return
        try:
            delete_variable(variable_id)
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.refresh()
