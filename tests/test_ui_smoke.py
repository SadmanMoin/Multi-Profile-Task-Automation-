"""The control panel can be constructed without opening Chrome."""

from PySide6.QtWidgets import QApplication

from app.services.execution_service import reset_execution_service
from app.ui.main_window import MainWindow


def test_main_window_opens(db):
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.show()
        application.processEvents()
        assert window.windowTitle() == "Browser Task Automation"
        assert window.stack.count() == 7
        assert window.nav.count() == 7
        window.nav.setCurrentRow(1)
        application.processEvents()
        window.nav.setCurrentRow(2)
        window.nav.setCurrentRow(3)
        window.nav.setCurrentRow(6)
        application.processEvents()
    finally:
        window.close()
        application.processEvents()
        reset_execution_service()
