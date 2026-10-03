from app.models.workflow import ElementTarget, Workflow, WorkflowStep, step_summary
from app.services.workflow_service import (
    assign_profiles,
    assigned_profile_ids,
    delete_workflow,
    diff_versions,
    get_workflow,
    list_versions,
    rollback,
    save_workflow,
)
from app.utils.constants import ActionType
from tests.conftest import make_profile, make_workflow


def test_workflow_crud_assignment_and_summary(db):
    profile_a = make_profile("Profile 01")
    profile_b = make_profile("Profile 02")
    workflow = make_workflow()
    assert step_summary(workflow.steps[0]).startswith("Open ")
    assert 'Click "Connect"' == step_summary(workflow.steps[1])
    assign_profiles(workflow.id, [profile_a.id, profile_b.id, profile_a.id])
    assert assigned_profile_ids(workflow.id) == [profile_a.id, profile_b.id]
    delete_workflow(workflow.id)
    from app.services.workflow_service import list_workflows

    assert list_workflows() == []


def test_version_bump_diff_and_rollback(db):
    workflow = make_workflow()
    assert workflow.version == 1
    edited = save_workflow(
        workflow,
        [
            WorkflowStep(step_number=1, action_type=ActionType.OPEN_URL, value="https://example.test/tasks"),
            workflow.steps[1],
        ],
    )
    assert edited.version == 2
    versions = [item[0] for item in list_versions(edited.id)]
    assert versions == [1, 2]
    difference = diff_versions(edited.id, 1, 2)
    assert "example.test/tasks" in difference
    restored = rollback(edited.id, 1)
    assert restored.version == 3
    assert restored.steps[0].value == "https://example.test"


def test_password_step_never_stores_the_typed_secret(db):
    workflow = save_workflow(
        Workflow(name="Login"),
        [
            WorkflowStep(
                step_number=1,
                action_type=ActionType.TYPE,
                target=ElementTarget(tag="input", input_type="password", name="Password"),
                value="super-secret-password",
            )
        ],
    )
    assert workflow.steps[0].value == "{{PASSWORD}}"
    assert "super-secret-password" not in workflow.model_dump_json()
    reloaded = get_workflow(workflow.id)
    assert "super-secret-password" not in reloaded.model_dump_json()
