import json

from app.services.workflow_service import deserialize_workflow, serialize_workflow
from tests.conftest import make_workflow


def test_workflow_round_trip(db):
    workflow = make_workflow()
    payload = serialize_workflow(workflow)
    encoded = json.dumps(payload)
    restored = deserialize_workflow(json.loads(encoded))
    assert restored.name == workflow.name
    assert restored.steps[1].target.role == "button"
    assert restored.steps[1].target.name == "Connect"
    assert restored.steps[1].retry_count == 2


def test_saved_workflow_file_hides_secrets(db, tmp_path):
    from app.models.workflow import ElementTarget, Workflow, WorkflowStep
    from app.services.workflow_service import save_workflow
    from app.utils.constants import ActionType
    from app.utils.paths import get_workflows_dir

    save_workflow(
        Workflow(name="Secrets"),
        [
            WorkflowStep(
                step_number=1,
                action_type=ActionType.TYPE,
                target=ElementTarget(input_type="password"),
                value="seed phrase words should not be saved",
            )
        ],
    )
    files = list(get_workflows_dir().glob("*.json"))
    assert files
    text = files[0].read_text(encoding="utf-8")
    assert "seed phrase words" not in text
    assert "{{PASSWORD}}" in text
