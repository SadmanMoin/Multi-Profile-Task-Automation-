"""Encrypt profile variable values at rest with a local key file.

The key never leaves this PC. Decrypted values stay in memory and must not be logged.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.utils.paths import get_data_dir


def _key_path():
    return get_data_dir() / ".secret_key"


def _fernet() -> Fernet:
    path = _key_path()
    if not path.exists():
        path.write_bytes(Fernet.generate_key())
    return Fernet(path.read_bytes())


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Stored value could not be decrypted") from exc
