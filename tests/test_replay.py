from app.automation.control import RunControl
from app.automation.replay_engine import NullHooks, ReplayEngine
from app.models.workflow import ElementTarget, WorkflowStep
from app.utils.constants import ActionType, RunStatus, VerificationType
from tests.fakes import FakeSession


def _engine(session, steps, **kwargs):
    control = kwargs.pop("control", None) or RunControl()
    hooks = kwargs.pop("hooks", None) or NullHooks()
    engine = ReplayEngine(session, control, hooks, kwargs.pop("variables", {}), **kwargs)
    return engine.run(steps), engine


def test_replay_runs_steps_in_order():
    session = FakeSession()
    steps = [
        WorkflowStep(step_number=1, action_type=ActionType.OPEN_URL, value="https://example.test"),
        WorkflowStep(
            step_number=2,
            action_type=ActionType.CLICK,
            target=ElementTarget(role="button", name="Connect"),
        ),
    ]
    status, _engine_obj = _engine(session, steps)
    assert status == RunStatus.COMPLETED
    assert session.actions[0][0] == ActionType.OPEN_URL
    assert session.actions[1][0] == ActionType.CLICK


def test_retry_then_success_and_exhausted_failure():
    session = FakeSession()
    session.failures_left[1] = 2
    steps = [
        WorkflowStep(
            step_number=1,
            action_type=ActionType.CLICK,
            target=ElementTarget(name="Connect"),
            retry_count=2,
            retry_delay_ms=0,
        )
    ]
    status, _engine_obj = _engine(session, steps)
    assert status == RunStatus.COMPLETED
    assert [item[0] for item in session.actions].count(ActionType.CLICK) == 3

    session = FakeSession()
    session.failures_left[1] = 5
    status, _engine_obj = _engine(session, steps)
    assert status == RunStatus.FAILED
    assert [item[0] for item in session.actions].count(ActionType.CLICK) == 3


def test_verification_failure_retries():
    session = FakeSession()
    session.fail_verification = True
    steps = [
        WorkflowStep(
            step_number=1,
            action_type=ActionType.CLICK,
            target=ElementTarget(name="Submit"),
            verification_type=VerificationType.TEXT_VISIBLE,
            verification_expected="Completed",
            retry_count=1,
            retry_delay_ms=0,
        )
    ]
    status, _engine_obj = _engine(session, steps)
    assert status == RunStatus.FAILED
    assert [item[0] for item in session.actions].count(ActionType.CLICK) == 2


def test_already_completed_skips_the_action():
    session = FakeSession()
    session.already_complete = True
    steps = [
        WorkflowStep(
            step_number=1,
            action_type=ActionType.CLICK,
            target=ElementTarget(name="Submit"),
            verification_type=VerificationType.TEXT_VISIBLE,
            verification_expected="Completed",
            skip_if_already_complete=True,
        )
    ]
    status, _engine_obj = _engine(session, steps)
    assert status == RunStatus.COMPLETED
    assert ActionType.CLICK not in [item[0] for item in session.actions]
    assert session.actions[0][0] == "VERIFY"


def test_dry_run_does_not_click_or_type():
    session = FakeSession()
    steps = [
        WorkflowStep(step_number=1, action_type=ActionType.OPEN_URL, value="https://example.test"),
        WorkflowStep(step_number=2, action_type=ActionType.CLICK, target=ElementTarget(name="Submit")),
        WorkflowStep(
            step_number=3,
            action_type=ActionType.TYPE,
            target=ElementTarget(name="Note", placeholder="Required value"),
            value="hello",
        ),
    ]
    status, _engine_obj = _engine(session, steps, dry_run=True)
    assert status == RunStatus.COMPLETED
    kinds = [item[0] for item in session.actions]
    assert ActionType.OPEN_URL in kinds
    assert ActionType.CLICK not in kinds
    assert ActionType.TYPE not in kinds
    assert kinds.count("LOCATE") == 2


def test_human_verification_pauses_and_does_not_keep_a_secret_in_the_reason():
    session = FakeSession()
    session.challenge = True
    control = RunControl()
    seen = []

    class Hooks(NullHooks):
        def manual_action(self, step, reason):
            seen.append(reason)
            session.challenge = False
            control.resume()

    steps = [
        WorkflowStep(
            step_number=1,
            action_type=ActionType.TYPE,
            target=ElementTarget(name="Note"),
            value="{{PASSWORD}}",
        )
    ]

    def run():
        engine = ReplayEngine(
            session,
            control,
            Hooks(),
            {"PASSWORD": "top-secret-value"},
            secret_values=["top-secret-value"],
        )
        return engine.run(steps)

    status = run()
    assert status == RunStatus.COMPLETED
    assert seen == ["Human verification detected"]
    assert "top-secret-value" not in " ".join(seen)
    assert session.actions[-1][1] == "top-secret-value"


def test_missing_variable_waits_for_the_user():
    session = FakeSession()
    control = RunControl()

    class Hooks(NullHooks):
        def __init__(self):
            self.engine = None

        def manual_action(self, step, reason):
            assert "{{PASSWORD}}" in reason
            self.engine.variables["PASSWORD"] = "later"
            control.resume()

    hooks = Hooks()
    engine = ReplayEngine(session, control, hooks, {})
    hooks.engine = engine
    status = engine.run(
        [
            WorkflowStep(
                step_number=1,
                action_type=ActionType.TYPE,
                target=ElementTarget(name="Password", input_type="text"),
                value="{{PASSWORD}}",
            )
        ]
    )
    assert status == RunStatus.COMPLETED
    assert session.actions[-1][1] == "later"
