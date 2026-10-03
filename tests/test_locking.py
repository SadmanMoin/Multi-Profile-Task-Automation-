import os

from app.database.database import session_scope
from app.database.models import ProfileRow
from app.database.repositories import acquire_lock, get_profile, release_lock
from app.utils.constants import LockKind
from app.utils.process import pid_alive, terminate_automation_chrome
from tests.conftest import make_profile


def test_profile_lock_blocks_a_second_live_owner_and_releases(db):
    profile = make_profile()
    assert acquire_lock(profile.id, owner_pid=os.getpid(), run_id=1, kind=LockKind.RUN)
    assert not acquire_lock(profile.id, owner_pid=os.getpid(), run_id=2, kind=LockKind.RUN)
    release_lock(profile.id, run_id=1)
    assert acquire_lock(profile.id, owner_pid=os.getpid(), run_id=2, kind=LockKind.RUN)
    release_lock(profile.id, run_id=2)
    assert get_profile(profile.id).lock_owner_pid is None


def test_stale_lock_from_a_dead_process_can_be_replaced(db):
    profile = make_profile()
    with session_scope() as session:
        row = session.get(ProfileRow, profile.id)
        row.lock_owner_pid = 99999999
        row.lock_run_id = 4
        row.lock_kind = LockKind.RUN
    assert pid_alive(99999999) is False
    assert acquire_lock(profile.id, owner_pid=os.getpid(), run_id=5, kind=LockKind.RUN)
    assert get_profile(profile.id).lock_run_id == 5


def test_terminate_refuses_a_non_chrome_process():
    assert terminate_automation_chrome(os.getpid(), r"C:\Chrome\User Data") is False
    assert pid_alive(os.getpid()) is True
