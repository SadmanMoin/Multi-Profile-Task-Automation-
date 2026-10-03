"""Overview counts and the latest runs."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QTableWidget, QVBoxLayout, QWidget

from app.database import repositories
from app.ui.widgets import StatCard, configure_table, fill_table, page_title
from app.utils.timeutil import format_local


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.cards = {
            "profiles": StatCard("Total Profiles"),
            "running": StatCard("Running"),
            "queued": StatCard("Queued"),
            "completed": StatCard("Completed"),
            "failed": StatCard("Failed"),
            "paused": StatCard("Paused"),
            "manual": StatCard("Manual Action Required"),
        }
        grid = QGridLayout()
        for index, card in enumerate(self.cards.values()):
            grid.addWidget(card, index // 4, index % 4)
        self.table = QTableWidget()
        configure_table(self.table, ["Profile", "Workflow", "Status", "Step", "Updated", "Error"])
        layout = QVBoxLayout(self)
        layout.addWidget(page_title("Dashboard", "One view of every profile and workflow run on this PC."))
        layout.addLayout(grid)
        layout.addWidget(self.table, 1)

    def refresh(self) -> None:
        counts = repositories.dashboard_counts()
        self.cards["profiles"].set_value(counts.profiles)
        self.cards["running"].set_value(counts.running)
        self.cards["queued"].set_value(counts.queued)
        self.cards["completed"].set_value(counts.completed)
        self.cards["failed"].set_value(counts.failed)
        self.cards["paused"].set_value(counts.paused)
        self.cards["manual"].set_value(counts.manual_action_required)
        rows = []
        for run in repositories.list_task_runs(limit=12):
            rows.append(
                [
                    run.profile_name,
                    run.workflow_name,
                    run.status,
                    run.current_step_number or "",
                    format_local(run.updated_at, with_date=False),
                    run.error,
                ]
            )
        fill_table(self.table, rows)
