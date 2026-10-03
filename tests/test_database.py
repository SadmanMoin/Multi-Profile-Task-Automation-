from sqlalchemy import inspect

from app.database.database import check_database
from app.database.models import ProfileRow, SettingRow, WorkflowRow
from app.services.settings_service import get_setting


def test_schema_and_default_settings(db):
    check_database()
    from app.database.database import _engine

    assert _engine is not None
    names = set(inspect(_engine).get_table_names())
    expected = {
        "profiles",
        "profile_variables",
        "workflows",
        "workflow_steps",
        "workflow_variables",
        "workflow_versions",
        "workflow_assignments",
        "task_runs",
        "step_runs",
        "activity_logs",
        "manual_actions",
        "settings",
    }
    assert expected <= names
    assert get_setting("max_concurrent_browsers") == "3"
    assert get_setting("schema_version") == "1"


def test_tables_are_sqlalchemy_models():
    assert ProfileRow.__tablename__ == "profiles"
    assert WorkflowRow.__tablename__ == "workflows"
    assert SettingRow.__tablename__ == "settings"
