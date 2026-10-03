"""Add, edit, test, and launch Chrome profiles."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QPushButton, QTableWidget, QVBoxLayout, QWidget

from app.services.errors import ServiceError
from app.services.profile_service import (
    create_profile,
    delete_profile,
    launch_profile,
    list_profiles,
    set_enabled,
    status_label,
    test_profile,
    update_profile,
)
from app.ui.dialogs.profile_dialog import ProfileDialog
from app.ui.dialogs.variable_dialog import VariableDialog
from app.ui.widgets import button_row, configure_table, confirm, fill_table, page_title, selected_id, show_error
from app.utils.timeutil import format_local


class _CallThread(QThread):
    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(self, func) -> None:
        super().__init__()
        self.func = func

    def run(self) -> None:
        try:
            result = self.func()
            self.succeeded.emit("" if result is None else str(result))
        except Exception as exc:
            self.failed.emit(str(exc))


class ProfilePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._thread: _CallThread | None = None
        self.table = QTableWidget()
        configure_table(
            self.table,
            ["Name", "Status", "Chrome profile", "User data", "Enabled", "Updated"],
        )
        add = QPushButton("Add")
        edit = QPushButton("Edit")
        delete = QPushButton("Delete")
        toggle = QPushButton("Enable / Disable")
        test = QPushButton("Test")
        launch = QPushButton("Launch")
        variables = QPushButton("Variables")
        add.setObjectName("primary")
        add.clicked.connect(self._add)
        edit.clicked.connect(self._edit)
        delete.clicked.connect(self._delete)
        toggle.clicked.connect(self._toggle)
        test.clicked.connect(self._test)
        launch.clicked.connect(self._launch)
        variables.clicked.connect(self._variables)
        layout = QVBoxLayout(self)
        layout.addWidget(
            page_title(
                "Profiles",
                "Each profile uses its own Chrome user data. Cookies and sessions are not shared. "
                "The app does not create accounts.",
            )
        )
        layout.addLayout(button_row(add, edit, delete, toggle, test, launch, variables))
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        rows = []
        ids = []
        for profile in list_profiles():
            rows.append(
                [
                    profile.name,
                    status_label(profile),
                    profile.chrome_profile_directory,
                    profile.user_data_dir,
                    "yes" if profile.enabled else "no",
                    format_local(profile.updated_at),
                ]
            )
            ids.append(profile.id or 0)
        fill_table(self.table, rows, ids)

    def _selected_profile(self):
        profile_id = selected_id(self.table)
        if profile_id is None:
            QMessageBox.information(self, "Profiles", "Select a profile first.")
            return None
        for profile in list_profiles():
            if profile.id == profile_id:
                return profile
        return None

    def _add(self) -> None:
        dialog = ProfileDialog(parent=self)
        if dialog.exec() != ProfileDialog.DialogCode.Accepted:
            return
        try:
            create_profile(dialog.to_profile())
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.refresh()

    def _edit(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        dialog = ProfileDialog(profile, self)
        if dialog.exec() != ProfileDialog.DialogCode.Accepted:
            return
        try:
            update_profile(dialog.to_profile())
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.refresh()

    def _delete(self) -> None:
        profile = self._selected_profile()
        if profile is None or profile.id is None:
            return
        if not confirm(self, f"Remove {profile.name} from the app? Chrome user data will not be deleted."):
            return
        try:
            delete_profile(profile.id)
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.refresh()

    def _toggle(self) -> None:
        profile = self._selected_profile()
        if profile is None or profile.id is None:
            return
        try:
            set_enabled(profile.id, not profile.enabled)
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.refresh()

    def _run_background(self, func, success: str) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.information(self, "Profiles", "A profile test is already running.")
            return
        self._thread = _CallThread(func)
        self._thread.succeeded.connect(lambda message: QMessageBox.information(self, "Profiles", message or success))
        self._thread.failed.connect(lambda message: QMessageBox.critical(self, "Profiles", message))
        self._thread.finished.connect(self.refresh)
        self._thread.start()

    def _test(self) -> None:
        profile = self._selected_profile()
        if profile is None or profile.id is None:
            return
        profile_id = profile.id
        self._run_background(lambda: test_profile(profile_id), "Profile test finished.")

    def _launch(self) -> None:
        profile = self._selected_profile()
        if profile is None or profile.id is None:
            return
        try:
            launch_profile(profile.id)
        except ServiceError as exc:
            show_error(self, exc)

    def _variables(self) -> None:
        profile = self._selected_profile()
        if profile is None or profile.id is None:
            return
        VariableDialog(profile.id, self).exec()
