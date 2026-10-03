"""Add or edit a Chrome profile record."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.models.profile import Profile
from app.services.profile_service import default_chrome_path, default_user_data_dir, discover_chrome_profiles


class ProfileDialog(QDialog):
    def __init__(self, profile: Profile | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit profile" if profile else "Add profile")
        self.resize(640, 320)
        self._profile_id = profile.id if profile else None

        self.name = QLineEdit(profile.name if profile else "")
        self.chrome = QLineEdit(profile.chrome_executable_path if profile else default_chrome_path())
        self.user_data = QLineEdit(profile.user_data_dir if profile else default_user_data_dir())
        self.directory = QComboBox()
        self.directory.setEditable(True)
        self.enabled = QCheckBox("Enabled")
        self.enabled.setChecked(True if profile is None else profile.enabled)
        self.notes = QLineEdit(profile.notes if profile else "")

        chrome_row = QHBoxLayout()
        chrome_row.addWidget(self.chrome)
        browse_chrome = QPushButton("Browse")
        browse_chrome.clicked.connect(self._browse_chrome)
        chrome_row.addWidget(browse_chrome)

        data_row = QHBoxLayout()
        data_row.addWidget(self.user_data)
        browse_data = QPushButton("Browse")
        browse_data.clicked.connect(self._browse_data)
        data_row.addWidget(browse_data)

        form = QFormLayout()
        form.addRow("Profile name", self.name)
        form.addRow("Chrome executable", chrome_row)
        form.addRow("User data directory", data_row)
        form.addRow("Chrome profile", self.directory)
        form.addRow("", self.enabled)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.user_data.editingFinished.connect(self._load_directories)
        self._load_directories()
        if profile is not None:
            self.directory.setCurrentText(profile.chrome_profile_directory)

    def _browse_chrome(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Chrome executable", self.chrome.text(), "Executable (*.exe)")
        if path:
            self.chrome.setText(path)

    def _browse_data(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Chrome user data", self.user_data.text())
        if path:
            self.user_data.setText(path)
            self._load_directories()

    def _load_directories(self) -> None:
        current = self.directory.currentText().strip() or "Default"
        self.directory.clear()
        discovered = discover_chrome_profiles(self.user_data.text().strip())
        if not discovered:
            self.directory.addItem("Default", "Default")
        for directory, display in discovered:
            label = f"{directory} — {display}" if display else directory
            self.directory.addItem(label, directory)
        index = self.directory.findData(current)
        if index >= 0:
            self.directory.setCurrentIndex(index)
        else:
            self.directory.setCurrentText(current)

    def _accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Profile", "Profile name is required.")
            return
        chrome = self.chrome.text().strip()
        user_data = self.user_data.text().strip()
        missing = []
        if not Path(chrome).is_file():
            missing.append("Chrome executable was not found.")
        if not Path(user_data).is_dir():
            missing.append("User data directory was not found.")
        if missing:
            answer = QMessageBox.question(
                self,
                "Profile",
                "\n".join(missing) + "\n\nSave the profile anyway?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.accept()

    def to_profile(self) -> Profile:
        directory = self.directory.currentData() or self.directory.currentText().strip() or "Default"
        return Profile(
            id=self._profile_id,
            name=self.name.text().strip(),
            chrome_executable_path=self.chrome.text().strip(),
            user_data_dir=self.user_data.text().strip(),
            chrome_profile_directory=str(directory).strip() or "Default",
            enabled=self.enabled.isChecked(),
            notes=self.notes.text().strip(),
        )
