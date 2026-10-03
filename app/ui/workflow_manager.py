"""Review, assign, and version saved workflows."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.models.workflow import Workflow
from app.services.errors import ServiceError
from app.services.execution_service import get_execution_service
from app.services.workflow_service import (
    assign_profiles,
    assigned_profile_ids,
    delete_workflow,
    get_workflow,
    list_workflows,
    save_workflow,
)
from app.ui.dialogs.assign_dialog import AssignDialog
from app.ui.dialogs.run_dialog import RunDialog
from app.ui.dialogs.versions_dialog import VersionsDialog
from app.ui.step_editor import StepEditor
from app.ui.widgets import button_row, configure_table, confirm, fill_table, page_title, selected_id, show_error
from app.utils.timeutil import format_local


class WorkflowEditor(QDialog):
    def __init__(self, workflow: Workflow, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(workflow.name)
        self.resize(760, 560)
        self.workflow_id = workflow.id
        self.name = QLineEdit(workflow.name)
        self.description = QLineEdit(workflow.description)
        self.editor = StepEditor()
        self.editor.set_steps(workflow.steps)
        save = QPushButton("Save Workflow")
        save.setObjectName("primary")
        save.clicked.connect(self._save)
        layout = QVBoxLayout(self)
        layout.addWidget(self.name)
        layout.addWidget(self.description)
        layout.addWidget(self.editor, 1)
        layout.addWidget(save)

    def _save(self) -> None:
        try:
            saved = save_workflow(
                Workflow(id=self.workflow_id, name=self.name.text(), description=self.description.text()),
                self.editor.get_steps(),
            )
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.workflow_id = saved.id
        QMessageBox.information(self, "Workflow", f"Saved {saved.name} v{saved.version}.")
        self.accept()


class WorkflowPage(QWidget):
    def __init__(self, open_learn) -> None:
        super().__init__()
        self._open_learn = open_learn
        self.table = QTableWidget()
        configure_table(self.table, ["Name", "Version", "Steps", "Updated", "Description"])
        new = QPushButton("New Workflow")
        edit = QPushButton("Edit")
        delete = QPushButton("Delete")
        assign = QPushButton("Assign")
        versions = QPushButton("Versions")
        run = QPushButton("Run")
        new.setObjectName("primary")
        run.setObjectName("primary")
        new.clicked.connect(self._new)
        edit.clicked.connect(self._edit)
        delete.clicked.connect(self._delete)
        assign.clicked.connect(self._assign)
        versions.clicked.connect(self._versions)
        run.clicked.connect(self._run)
        layout = QVBoxLayout(self)
        layout.addWidget(page_title("Workflows", "Save a recording, assign profiles, then run it yourself."))
        layout.addLayout(button_row(new, edit, delete, assign, versions, run))
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        rows = []
        ids = []
        for workflow in list_workflows():
            rows.append(
                [
                    workflow.name,
                    f"v{workflow.version}",
                    len(workflow.steps),
                    format_local(workflow.updated_at),
                    workflow.description,
                ]
            )
            ids.append(workflow.id or 0)
        fill_table(self.table, rows, ids)

    def _selected(self) -> Workflow | None:
        workflow_id = selected_id(self.table)
        if workflow_id is None:
            QMessageBox.information(self, "Workflows", "Select a workflow first.")
            return None
        try:
            return get_workflow(workflow_id)
        except ServiceError as exc:
            show_error(self, exc)
            return None

    def _new(self) -> None:
        self._open_learn()

    def _edit(self) -> None:
        workflow = self._selected()
        if workflow is None:
            return
        WorkflowEditor(workflow, self).exec()
        self.refresh()

    def _delete(self) -> None:
        workflow = self._selected()
        if workflow is None or workflow.id is None:
            return
        if not confirm(self, f"Delete {workflow.name}? Past run history is kept."):
            return
        try:
            delete_workflow(workflow.id)
        except ServiceError as exc:
            show_error(self, exc)
            return
        self.refresh()

    def _assign(self) -> None:
        workflow = self._selected()
        if workflow is None or workflow.id is None:
            return
        dialog = AssignDialog(workflow.name, assigned_profile_ids(workflow.id), self)
        if dialog.exec() != AssignDialog.DialogCode.Accepted:
            return
        try:
            assign_profiles(workflow.id, dialog.selected_ids())
        except ServiceError as exc:
            show_error(self, exc)
            return
        QMessageBox.information(self, "Assign", "Profiles were assigned. Nothing was started.")

    def _versions(self) -> None:
        workflow = self._selected()
        if workflow is None or workflow.id is None:
            return
        VersionsDialog(workflow.id, self).exec()
        self.refresh()

    def _run(self) -> None:
        workflow = self._selected()
        if workflow is None or workflow.id is None:
            return
        dialog = RunDialog(workflow, assigned_profile_ids(workflow.id), self)
        if dialog.exec() != RunDialog.DialogCode.Accepted:
            return
        try:
            get_execution_service().enqueue(workflow.id, dialog.selected_ids(), dry_run=dialog.dry_run.isChecked())
        except ServiceError as exc:
            show_error(self, exc)
            return
        QMessageBox.information(self, "Run", "The workflow was queued. Watch it on Runs.")
