"""Compare workflow versions and roll back."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.services.errors import ServiceError
from app.services.workflow_service import diff_versions, list_versions, rollback
from app.ui.widgets import confirm, show_error
from app.utils.timeutil import format_local


class VersionsDialog(QDialog):
    def __init__(self, workflow_id: int, parent=None) -> None:
        super().__init__(parent)
        self.workflow_id = workflow_id
        self.setWindowTitle("Workflow versions")
        self.resize(720, 460)
        self.rolled_back = False
        self.versions = QListWidget()
        self.diff = QPlainTextEdit()
        self.diff.setReadOnly(True)
        compare = QPushButton("Compare selected with current")
        compare.clicked.connect(self._compare)
        restore = QPushButton("Roll back to selected")
        restore.clicked.connect(self._rollback)
        left = QVBoxLayout()
        left.addWidget(QLabel("Saved versions"))
        left.addWidget(self.versions)
        left.addWidget(compare)
        left.addWidget(restore)
        row = QHBoxLayout()
        row.addLayout(left, 1)
        row.addWidget(self.diff, 2)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        self._load()

    def _load(self) -> None:
        self.versions.clear()
        for version, created in list_versions(self.workflow_id):
            self.versions.addItem(f"v{version}  {format_local(created)}")
            self.versions.item(self.versions.count() - 1).setData(256, version)

    def _selected_version(self) -> int | None:
        item = self.versions.currentItem()
        if item is None:
            return None
        value = item.data(256)
        return int(value) if value is not None else None

    def _compare(self) -> None:
        version = self._selected_version()
        versions = list_versions(self.workflow_id)
        if version is None or not versions:
            return
        current = versions[-1][0]
        try:
            self.diff.setPlainText(diff_versions(self.workflow_id, version, current))
        except ServiceError as exc:
            show_error(self, exc)

    def _rollback(self) -> None:
        version = self._selected_version()
        if version is None:
            return
        if not confirm(self, f"Create a new version from v{version}?"):
            return
        try:
            restored = rollback(self.workflow_id, version)
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.rolled_back = True
        QMessageBox.information(self, "Workflow versions", f"Current workflow is now v{restored.version}.")
        self._load()
