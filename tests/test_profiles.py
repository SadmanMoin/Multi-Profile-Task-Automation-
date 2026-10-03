import pytest

from app.services.errors import ServiceError
from app.services.profile_service import (
    create_profile,
    delete_profile,
    list_profiles,
    save_variable,
    set_enabled,
    status_label,
    update_profile,
)
from app.utils.crypto import decrypt_text
from app.database.repositories import get_profile_variable_secret
from tests.conftest import make_profile
from app.models.profile import Profile


def test_profile_crud(db):
    created = make_profile("Profile 01")
    assert created.id is not None
    assert status_label(created) == "IDLE"
    created.name = "Profile 01b"
    updated = update_profile(created)
    assert updated.name == "Profile 01b"
    set_enabled(updated.id, False)
    assert status_label(list_profiles()[0]) == "DISABLED"
    delete_profile(updated.id)
    assert list_profiles() == []


def test_duplicate_profile_name_is_rejected(db):
    make_profile("Profile 01")
    with pytest.raises(ServiceError):
        make_profile("Profile 01")


def test_profile_variable_is_encrypted_at_rest(db):
    profile = make_profile()
    save_variable(profile.id, "password", "correct-horse", is_secret=True)
    stored = get_profile_variable_secret(profile.id, "PASSWORD")
    assert stored is not None
    encrypted, is_secret = stored
    assert is_secret is True
    assert "correct-horse" not in encrypted
    assert decrypt_text(encrypted) == "correct-horse"


def test_blank_secret_update_keeps_old_value(db):
    profile = make_profile()
    save_variable(profile.id, "API_KEY", "abc123", is_secret=True)
    save_variable(profile.id, "API_KEY", "", is_secret=True)
    encrypted, _ = get_profile_variable_secret(profile.id, "API_KEY")
    assert decrypt_text(encrypted) == "abc123"


def test_create_requires_a_name(db):
    with pytest.raises(ServiceError):
        create_profile(
            Profile(
                name="  ",
                chrome_executable_path="chrome.exe",
                user_data_dir="data",
                chrome_profile_directory="Default",
            )
        )
