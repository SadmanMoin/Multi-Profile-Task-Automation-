"""Main control panel window."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app.database import repositories
from app.services.execution_service import get_execution_service
from app.services.recovery_service import recover_on_startup
from app.ui.dashboard import DashboardPage
from app.ui.learn_mode import LearnPage
from app.ui.logs_view import LogsPage
from app.ui.run_monitor import RunPage
from app.ui.profile_manager import ProfilePage
from app.ui.settings_page import SettingsPage
from app.ui.workflow_manager import WorkflowPage
from app.utils.constants import NAV_ITEMS, RunStatus


class _Bridge(QObject):
    notify = Signal(str, str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Browser Task Automation")
        self.resize(1180, 760)
        self.execution = get_execution_service()
        self._seen_manual: set[int] = set()
        self.bridge = _Bridge()
        self.bridge.notify.connect(self._on_notify)
        self.execution.add_listener(self._listener)

        self.learn_page = LearnPage(open_workflows=self._open_workflows)
        self.run_page = RunPage(self.execution)
        self.pages = [
            DashboardPage(),
            ProfilePage(),
            WorkflowPage(self._open_learn),
            self.learn_page,
            self.run_page,
            LogsPage(),
            SettingsPage(),
        ]
        self.stack = QStackedWidget()
        for page in self.pages:
            self.stack.addWidget(page)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(180)
        self.nav.addItems(list(NAV_ITEMS))
        self.nav.currentRowChanged.connect(self._switch)
        brand = QLabel("Browser Task Automation")
        brand.setStyleSheet("font-size: 16px; font-weight: 600; padding: 12px 8px 4px 12px;")
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.addWidget(brand)
        side.addWidget(self.nav, 1)
        side_widget = QWidget()
        side_widget.setLayout(side)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        content.addWidget(side_widget)
        content.addWidget(self.stack, 1)
        holder = QWidget()
        holder.setLayout(content)
        self.setCentralWidget(holder)

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip("Browser Task Automation")
        self.tray.show()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        self.menuBar().addMenu("File").addAction(quit_action)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self.nav.setCurrentRow(0)

        messages = recover_on_startup()
        if messages:
            QMessageBox.information(self, "Recovery", "\n".join(messages))
        self.execution.start()

    def _open_learn(self) -> None:
        index = list(NAV_ITEMS).index("Learn Mode")
        self.nav.setCurrentRow(index)
        self.learn_page.begin_new()

    def _open_workflows(self) -> None:
        self.nav.setCurrentRow(list(NAV_ITEMS).index("Workflows"))

    def _switch(self, index: int) -> None:
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        self._refresh_current()

    def _refresh_current(self) -> None:
        page = self.stack.currentWidget()
        refresh = getattr(page, "refresh", None)
        if refresh:
            refresh()

    def _tick(self) -> None:
        # Settings and Learn Mode keep their own edits. Live pages refresh in the background.
        if self.stack.currentIndex() in (0, 1, 4, 5):
            self._refresh_current()
        self._scan_manual(notify=False)

    def _listener(self, status: str, message: str) -> None:
        self.bridge.notify.emit(status, message)

    def _on_notify(self, status: str, message: str) -> None:
        if status not in (RunStatus.FAILED, RunStatus.MANUAL_ACTION_REQUIRED):
            return
        title = "Manual action required" if status == RunStatus.MANUAL_ACTION_REQUIRED else "Run failed"
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 8000)
        if status == RunStatus.MANUAL_ACTION_REQUIRED:
            self._scan_manual(notify=True)

    def _scan_manual(self, notify: bool) -> None:
        for action in repositories.list_manual_actions(open_only=True):
            if action.id is None or action.id in self._seen_manual:
                continue
            self._seen_manual.add(action.id)
            if notify:
                self.run_page.show_manual(action.id)

    def closeEvent(self, event) -> None:
        if self.execution.active_count():
            answer = QMessageBox.question(
                self,
                "Quit",
                "A workflow is still active. Stop it and quit?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.timer.stop()
        self.execution.shutdown()
        self.tray.hide()
        event.accept()
