"""Queue, pause, resume, stop, and the manual-action inbox."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import repositories
from app.services.errors import ServiceError
from app.services.execution_service import ExecutionService, get_execution_service
from app.ui.dialogs.manual_dialog import ManualActionDialog
from app.ui.widgets import configure_table, fill_table, page_title, selected_id, show_error
from app.utils.constants import RunStatus
from app.utils.timeutil import format_local


class RunPage(QWidget):
    def __init__(self, execution: ExecutionService | None = None) -> None:
        super().__init__()
        self.execution = execution or get_execution_service()
        self._dialogs: list[ManualActionDialog] = []
        self.runs = QTableWidget()
        configure_table(self.runs, ["ID", "Profile", "Workflow", "Status", "Step", "Dry run", "Error", "Updated"])
        self.steps = QTableWidget()
        configure_table(self.steps, ["Step", "Action", "Status", "Attempt", "Duration ms", "Error"])
        self.inbox = QTableWidget()
        configure_table(self.inbox, ["Profile", "Workflow", "Step", "Reason", "Opened"])
        self.runs.itemSelectionChanged.connect(self._show_steps)
        pause = QPushButton("Pause")
        resume = QPushButton("Resume")
        stop = QPushButton("Stop")
        stop.setObjectName("danger")
        focus = QPushButton("Open Browser")
        pause.clicked.connect(lambda: self._control("pause"))
        resume.clicked.connect(lambda: self._control("resume"))
        stop.clicked.connect(lambda: self._control("stop"))
        focus.clicked.connect(self._focus)
        inbox_resume = QPushButton("Resume")
        inbox_resume.setObjectName("primary")
        inbox_stop = QPushButton("Stop")
        inbox_open = QPushButton("Open Browser")
        inbox_resume.clicked.connect(self._inbox_resume)
        inbox_stop.clicked.connect(self._inbox_stop)
        inbox_open.clicked.connect(self._inbox_focus)
        controls = QHBoxLayout()
        for button in (pause, resume, stop, focus):
            controls.addWidget(button)
        controls.addStretch(1)
        inbox_controls = QHBoxLayout()
        for button in (inbox_open, inbox_resume, inbox_stop):
            inbox_controls.addWidget(button)
        inbox_controls.addStretch(1)
        runs_box = QWidget()
        runs_layout = QVBoxLayout(runs_box)
        runs_layout.setContentsMargins(0, 0, 0, 0)
        runs_layout.addLayout(controls)
        runs_layout.addWidget(self.runs, 1)
        runs_layout.addWidget(QLabel("Steps"))
        runs_layout.addWidget(self.steps, 1)
        inbox_box = QWidget()
        inbox_layout = QVBoxLayout(inbox_box)
        inbox_layout.setContentsMargins(0, 0, 0, 0)
        inbox_layout.addWidget(QLabel("Manual action inbox"))
        inbox_layout.addLayout(inbox_controls)
        inbox_layout.addWidget(self.inbox, 1)
        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Vertical)
        splitter.addWidget(runs_box)
        splitter.addWidget(inbox_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout = QVBoxLayout(self)
        layout.addWidget(
            page_title(
                "Runs",
                "Queued profiles wait for a free browser slot. Pause and resume keep the same step. "
                "Human verification stays here until you finish it.",
            )
        )
        layout.addWidget(splitter, 1)

    def refresh(self) -> None:
        rows = []
        ids = []
        for run in repositories.list_task_runs():
            rows.append(
                [
                    run.id,
                    run.profile_name,
                    run.workflow_name,
                    run.status,
                    run.current_step_number or "",
                    "yes" if run.dry_run else "",
                    run.error,
                    format_local(run.updated_at, with_date=False),
                ]
            )
            ids.append(run.id or 0)
        fill_table(self.runs, rows, ids)
        self._show_steps()
        actions = repositories.list_manual_actions(open_only=True)
        inbox_rows = []
        inbox_ids = []
        for action in actions:
            inbox_rows.append(
                [
                    action.profile_name,
                    action.workflow_name,
                    action.step_number,
                    action.reason,
                    format_local(action.created_at, with_date=False),
                ]
            )
            inbox_ids.append(action.id or 0)
        fill_table(self.inbox, inbox_rows, inbox_ids)

    def show_manual(self, action_id: int) -> None:
        action = next((item for item in repositories.list_manual_actions() if item.id == action_id), None)
        if action is None:
            return
        dialog = ManualActionDialog(action, self.execution, self)
        self._dialogs.append(dialog)
        dialog.show()

    def _selected_run_id(self) -> int | None:
        run_id = selected_id(self.runs)
        if run_id is None:
            QMessageBox.information(self, "Runs", "Select a run first.")
        return run_id

    def _show_steps(self) -> None:
        run_id = selected_id(self.runs)
        if run_id is None:
            fill_table(self.steps, [])
            return
        rows = []
        for step in repositories.list_step_runs(run_id):
            rows.append([step.step_number, step.action_type, step.status, step.attempt, step.duration_ms, step.error])
        fill_table(self.steps, rows)

    def _control(self, action: str) -> None:
        run_id = self._selected_run_id()
        if run_id is None:
            return
        if action == "pause":
            ok = self.execution.pause(run_id)
        elif action == "resume":
            ok = self.execution.resume(run_id)
        else:
            ok = self.execution.stop(run_id)
        if not ok:
            run = repositories.get_task_run(run_id)
            status = run.status if run else "unknown"
            QMessageBox.information(self, "Runs", f"Cannot {action} a run that is {status}.")
        self.refresh()

    def _focus(self) -> None:
        run_id = self._selected_run_id()
        if run_id is None:
            return
        try:
            self.execution.focus(run_id)
        except ServiceError as exc:
            show_error(self, exc)

    def _selected_manual(self):
        action_id = selected_id(self.inbox)
        if action_id is None:
            QMessageBox.information(self, "Manual action", "Select an inbox item first.")
            return None
        for action in repositories.list_manual_actions(open_only=True):
            if action.id == action_id:
                return action
        return None

    def _inbox_resume(self) -> None:
        action = self._selected_manual()
        if action is None:
            return
        self.execution.resume(action.task_run_id)
        self.refresh()

    def _inbox_stop(self) -> None:
        action = self._selected_manual()
        if action is None:
            return
        self.execution.stop(action.task_run_id)
        self.refresh()

    def _inbox_focus(self) -> None:
        action = self._selected_manual()
        if action is None:
            return
        try:
            self.execution.focus(action.task_run_id)
        except ServiceError as exc:
            show_error(self, exc)
