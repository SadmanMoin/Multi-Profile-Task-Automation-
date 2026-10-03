"""Start the local control panel."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.database.database import init_db
from app.ui.main_window import MainWindow
from app.ui.theme import STYLESHEET
from app.utils.logger import get_logger, setup_logging


def main() -> int:
    setup_logging()
    logger = get_logger("main")
    init_db()
    logger.info("Starting Browser Task Automation")
    application = QApplication(sys.argv)
    application.setStyle("Fusion")
    application.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
