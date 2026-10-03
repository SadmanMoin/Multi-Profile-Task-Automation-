"""Local limits and safety notes."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.services.settings_service import all_settings, set_setting
from app.ui.widgets import page_title
from app.utils.paths import get_data_dir, get_db_path, get_logs_dir


class SettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.concurrent = self._spin(1, 10)
        self.timeout = self._spin(1, 300)
        self.retry_count = self._spin(0, 10)
        self.retry_delay = self._spin(0, 120)
        self.disk = self._spin(50, 100000)
        form = QFormLayout()
        form.addRow("Maximum concurrent browsers", self.concurrent)
        form.addRow("Default step timeout (seconds)", self.timeout)
        form.addRow("Default retry count", self.retry_count)
        form.addRow("Default retry delay (seconds)", self.retry_delay)
        form.addRow("Minimum free disk (MB)", self.disk)
        save = QPushButton("Save settings")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        safety = QLabel(
            "This app automates only tasks you perform yourself.\n"
            "It does not solve CAPTCHAs, bypass anti-bot checks, spoof fingerprints, "
            "rotate proxies, or create accounts.\n"
            "If a human verification appears, the run pauses until you finish it and press Resume.\n\n"
            f"Version {__version__}\n"
            f"Database: {get_db_path()}\n"
            f"Logs: {get_logs_dir() / 'app.log'}\n"
            f"Data directory: {get_data_dir()}"
        )
        safety.setWordWrap(True)
        safety.setObjectName("hint")
        layout = QVBoxLayout(self)
        layout.addWidget(page_title("Settings", "Everything stays on this PC."))
        layout.addLayout(form)
        layout.addWidget(save)
        layout.addSpacing(12)
        layout.addWidget(safety)
        layout.addStretch(1)
        self.refresh()

    @staticmethod
    def _spin(low: int, high: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(low, high)
        return spin

    def refresh(self) -> None:
        values = all_settings()
        self.concurrent.setValue(int(values["max_concurrent_browsers"]))
        self.timeout.setValue(max(1, int(values["default_timeout_ms"]) // 1000))
        self.retry_count.setValue(int(values["default_retry_count"]))
        self.retry_delay.setValue(max(0, int(values["default_retry_delay_ms"]) // 1000))
        self.disk.setValue(int(values["min_free_disk_mb"]))

    def _save(self) -> None:
        set_setting("max_concurrent_browsers", str(self.concurrent.value()))
        set_setting("default_timeout_ms", str(self.timeout.value() * 1000))
        set_setting("default_retry_count", str(self.retry_count.value()))
        set_setting("default_retry_delay_ms", str(self.retry_delay.value() * 1000))
        set_setting("min_free_disk_mb", str(self.disk.value()))
        QMessageBox.information(self, "Settings", "Settings saved.")
