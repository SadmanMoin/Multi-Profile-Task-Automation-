"""Choose which queued runs can start without passing the concurrency limit."""

from __future__ import annotations

from app.models.execution import QueuePlan, TaskRun


def plan_queue(runs: list[TaskRun], locked_profile_ids: set[int], slots: int) -> QueuePlan:
    """Pick at most one run per profile, and never more than `slots` starts.

    A second run for a locked or already chosen profile stays queued.
    Runs that are only waiting for a free slot are not marked blocked.
    """
    start_ids: list[int] = []
    blocked_ids: list[int] = []
    seen: set[int] = set()
    for run in runs:
        if run.id is None or run.profile_id is None:
            continue
        if run.profile_id in locked_profile_ids or run.profile_id in seen:
            blocked_ids.append(run.id)
            continue
        if len(start_ids) >= max(0, slots):
            continue
        start_ids.append(run.id)
        seen.add(run.profile_id)
    return QueuePlan(start_ids=start_ids, blocked_ids=blocked_ids)
