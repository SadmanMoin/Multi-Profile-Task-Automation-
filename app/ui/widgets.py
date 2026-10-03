"""Small widgets shared by the control panel pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


STATUS_COLORS = {
    "QUEUED": "#b8bcc4",
    "RUNNING": "#7eb6ff",
    "PAUSED": "#e6b450",
    "COMPLETED": "#5dce8a",
    "FAILED": "#f07178",
    "MANUAL_ACTION_REQUIRED": "#d2a8ff",
    "STOPPED": "#9aa0a6",
    "SUCCESS": "#5dce8a",
    "FAILED_STEP": "#f07178",
    "RETRY": "#e6b450",
    "SKIPPED_ALREADY_COMPLETED": "#5dce8a",
    "IDLE": "#b8bcc4",
    "IN_USE": "#7eb6ff",
    "DISABLED": "#9aa0a6",
}


def page_title(text: str, hint: str = "") -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 8)
    title = QLabel(text)
    title.setStyleSheet("font-size: 20px; font-weight: 600;")
    layout.addWidget(title)
    if hint:
        muted = QLabel(hint)
        muted.setObjectName("hint")
        muted.setWordWrap(True)
        layout.addWidget(muted)
    return box


def button_row(*buttons: QPushButton) -> QHBoxLayout:
    layout = QHBoxLayout()
    for button in buttons:
        layout.addWidget(button)
    layout.addStretch(1)
    return layout


class StatCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        label = QLabel(title)
        label.setObjectName("muted")
        self.value = QLabel("0")
        self.value.setObjectName("stat")
        layout.addWidget(label)
        layout.addWidget(self.value)

    def set_value(self, number: int) -> None:
        self.value.setText(str(number))


def configure_table(table: QTableWidget, headers: list[str]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
    table.setShowGrid(False)


def fill_table(table: QTableWidget, rows: list[list[object]], row_ids: list[int] | None = None) -> None:
    selected = selected_id(table)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column, value in enumerate(row):
            text = "" if value is None else str(value)
            item = QTableWidgetItem(text)
            if column == 0 and row_ids is not None:
                item.setData(Qt.ItemDataRole.UserRole, row_ids[row_index])
            color = STATUS_COLORS.get(text)
            if color:
                item.setForeground(QColor(color))
            table.setItem(row_index, column, item)
        if row_ids is not None and row_ids[row_index] == selected:
            table.selectRow(row_index)


def selected_id(table: QTableWidget) -> int | None:
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    if item is None:
        return None
    value = item.data(Qt.ItemDataRole.UserRole)
    return int(value) if value is not None else None


def show_error(parent, exc: Exception) -> None:
    QMessageBox.critical(parent, "Browser Task Automation", str(exc))


def confirm(parent, text: str) -> bool:
    answer = QMessageBox.question(parent, "Browser Task Automation", text)
    return answer == QMessageBox.StandardButton.Yes
