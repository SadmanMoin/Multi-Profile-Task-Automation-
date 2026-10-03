"""Activity log. Secrets are redacted before they are stored."""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton, QTableWidget, QVBoxLayout, QWidget

from app.services.logging_service import export_csv, recent
from app.ui.widgets import button_row, configure_table, fill_table, page_title
from app.utils.timeutil import format_local


class LogsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.table = QTableWidget()
        configure_table(self.table, ["Time", "Profile", "Workflow", "Step", "Action", "Status", "Duration ms", "Error"])
        export = QPushButton("Export CSV")
        export.clicked.connect(self._export)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        layout = QVBoxLayout(self)
        layout.addWidget(page_title("Activity Logs", "Workflow events stay in the local database. Passwords are not logged."))
        layout.addLayout(button_row(refresh, export))
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        rows = []
        for entry in recent(500):
            rows.append(
                [
                    format_local(entry.created_at),
                    entry.profile_name,
                    entry.workflow_name,
                    "" if entry.step_number is None else entry.step_number,
                    entry.action,
                    entry.status,
                    entry.duration_ms,
                    entry.error,
                ]
            )
        fill_table(self.table, rows)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export activity log", "activity-log.csv", "CSV (*.csv)")
        if not path:
            return
        count = export_csv(path)
        QMessageBox.information(self, "Activity Logs", f"Exported {count} rows.")
