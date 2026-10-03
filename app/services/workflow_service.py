"""Save, version, assign, and compare workflows."""

from __future__ import annotations

import json
import re

from app.automation.secrets import find_variables, is_secret_variable, sanitize_type_value, sensitive_kind
from app.database import repositories
from app.models.workflow import Workflow, WorkflowStep, diff_workflows
from app.services.errors import ServiceError
from app.utils.constants import ActionType
from app.utils.logger import get_logger
from app.utils.paths import get_workflows_dir


logger = get_logger("workflows")


def list_workflows() -> list[Workflow]:
    return repositories.list_workflows()


def get_workflow(workflow_id: int) -> Workflow:
    workflow = repositories.get_workflow(workflow_id)
    if workflow is None:
        raise ServiceError("Workflow not found")
    return workflow


def protect_step(step: WorkflowStep) -> WorkflowStep:
    """Drop raw passwords and similar values before they are stored."""
    protected = step.model_copy(deep=True)
    if protected.action_type == ActionType.TYPE:
        protected.value = sanitize_type_value(
            protected.target,
            protected.value,
            sensitive=sensitive_kind(protected.target) is not None,
        )
    if sensitive_kind(protected.target):
        protected.target.text = ""
    return protected


def _signature(workflow: Workflow) -> str:
    payload = {
        "name": workflow.name,
        "description": workflow.description,
        "steps": [step.model_dump(exclude={"id", "workflow_id"}) for step in workflow.steps],
    }
    return json.dumps(payload, sort_keys=True)


def _sync_variables(workflow: Workflow) -> None:
    names = find_variables(*(step.value for step in workflow.steps))
    repositories.replace_workflow_variables(
        workflow.id,
        [(name, is_secret_variable(name)) for name in names],
    )


def _write_file(workflow: Workflow) -> None:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", workflow.name).strip("_") or "workflow"
    path = get_workflows_dir() / f"{workflow.id}-v{workflow.version}-{safe_name}.json"
    path.write_text(workflow.model_dump_json(indent=2), encoding="utf-8")


def save_workflow(workflow: Workflow, steps: list[WorkflowStep] | None = None) -> Workflow:
    if not workflow.name.strip():
        raise ServiceError("Workflow name is required")
    prepared = [protect_step(step) for step in (steps if steps is not None else workflow.steps)]
    for index, step in enumerate(prepared, start=1):
        step.step_number = index
    if workflow.id is None:
        created = repositories.create_workflow(workflow.name, workflow.description)
        repositories.replace_steps(created.id, prepared)
        _sync_variables(get_workflow(created.id))
        saved = get_workflow(created.id)
        repositories.add_workflow_snapshot(saved)
        _write_file(saved)
        logger.info("Saved workflow %s v%s", saved.name, saved.version)
        return saved

    current = get_workflow(workflow.id)
    repositories.update_workflow_meta(workflow.id, workflow.name, workflow.description)
    repositories.replace_steps(workflow.id, prepared)
    _sync_variables(get_workflow(workflow.id))
    updated = get_workflow(workflow.id)
    updated.version = current.version
    if _signature(current) != _signature(updated):
        repositories.set_workflow_version(workflow.id, current.version + 1)
        updated = get_workflow(workflow.id)
        repositories.add_workflow_snapshot(updated)
    _write_file(updated)
    logger.info("Saved workflow %s v%s", updated.name, updated.version)
    return updated


def delete_workflow(workflow_id: int) -> None:
    workflow = get_workflow(workflow_id)
    if repositories.workflow_has_active_run(workflow_id):
        raise ServiceError("Stop the active runs before deleting this workflow")
    repositories.delete_workflow(workflow_id)
    logger.info("Deleted workflow %s", workflow.name)


def assign_profiles(workflow_id: int, profile_ids: list[int]) -> None:
    get_workflow(workflow_id)
    unique_ids: list[int] = []
    for profile_id in profile_ids:
        profile = repositories.get_profile(profile_id)
        if profile is None:
            raise ServiceError("One of the selected profiles no longer exists")
        if profile_id not in unique_ids:
            unique_ids.append(profile_id)
    repositories.set_assignments(workflow_id, unique_ids)
    logger.info("Assigned workflow %s to %s profiles", workflow_id, len(unique_ids))


def assigned_profile_ids(workflow_id: int) -> list[int]:
    return repositories.list_assigned_profile_ids(workflow_id)


def list_versions(workflow_id: int) -> list[tuple[int, object]]:
    get_workflow(workflow_id)
    return repositories.list_workflow_versions(workflow_id)


def version_workflow(workflow_id: int, version: int) -> Workflow:
    snapshot = repositories.get_workflow_snapshot(workflow_id, version)
    if snapshot is None:
        raise ServiceError(f"Version {version} was not found")
    return Workflow.model_validate(snapshot)


def diff_versions(workflow_id: int, left_version: int, right_version: int) -> str:
    return diff_workflows(version_workflow(workflow_id, left_version), version_workflow(workflow_id, right_version))


def rollback(workflow_id: int, version: int) -> Workflow:
    source = version_workflow(workflow_id, version)
    current = get_workflow(workflow_id)
    restored = save_workflow(
        Workflow(
            id=workflow_id,
            name=source.name or current.name,
            description=source.description,
            version=current.version,
        ),
        source.steps,
    )
    logger.info("Rolled workflow %s back toward v%s as v%s", workflow_id, version, restored.version)
    return restored


def serialize_workflow(workflow: Workflow) -> dict:
    return workflow.model_dump(mode="json")


def deserialize_workflow(payload: dict) -> Workflow:
    return Workflow.model_validate(payload)
