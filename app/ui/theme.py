"""Control panel stylesheet."""

STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background: #1e1f24;
    color: #e8e8ea;
    font-size: 13px;
}
QListWidget#nav {
    background: #16171c;
    border: none;
    padding: 8px;
    outline: none;
}
QListWidget#nav::item {
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 2px;
}
QListWidget#nav::item:selected {
    background: #2d4a7a;
}
QFrame#card {
    background: #2a2b32;
    border-radius: 10px;
}
QLabel#stat {
    font-size: 28px;
    font-weight: 600;
}
QLabel#muted, QLabel#hint {
    color: #9a9aa3;
}
QPushButton {
    background: #34363f;
    border: 1px solid #454854;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover {
    background: #3e414c;
}
QPushButton:disabled {
    color: #777;
}
QPushButton#primary {
    background: #2d4a7a;
    border-color: #3d6cc2;
}
QPushButton#danger {
    background: #6e3036;
    border-color: #a14b55;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: #2a2b32;
    border: 1px solid #454854;
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: #2d4a7a;
}
QTableWidget {
    background: #23242a;
    alternate-background-color: #282a31;
    gridline-color: #34363f;
    border: none;
    selection-background-color: #2d4a7a;
}
QHeaderView::section {
    background: #2a2b32;
    color: #e8e8ea;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #454854;
}
QGroupBox {
    border: 1px solid #34363f;
    border-radius: 8px;
    margin-top: 12px;
    padding: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QCheckBox {
    spacing: 6px;
}
QScrollBar:vertical {
    background: #1e1f24;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #454854;
    border-radius: 4px;
}
"""
