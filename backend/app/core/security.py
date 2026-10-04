"""Passwords, random tokens and encryption of stored secrets."""

import base64
import hashlib
import re
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.errors import AppError

_hasher = PasswordHasher()  # Argon2id with the library's recommended parameters

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

# The most common passwords and college-specific guesses. Matching is case-insensitive.
COMMON_PASSWORDS = frozenset(
    [
        "password",
        "password1",
        "password12",
        "password123",
        "password1234",
        "passw0rd",
        "p@ssw0rd",
        "p@ssword",
        "123456789",
        "1234567890",
        "12345678910",
        "0123456789",
        "9876543210",
        "1111111111",
        "0000000000",
        "qwertyuiop",
        "qwerty1234",
        "qwerty12345",
        "1q2w3e4r5t",
        "1qaz2wsx3edc",
        "asdfghjkl",
        "zxcvbnm123",
        "iloveyou123",
        "welcome123",
        "welcome@123",
        "admin12345",
        "administrator",
        "letmein123",
        "abcd123456",
        "abc1234567",
        "abcdefghij",
        "princess123",
        "sunshine123",
        "football123",
        "cricket123",
        "india12345",
        "india@1234",
        "bharat1234",
        "mumbai1234",
        "pune123456",
        "college123",
        "college@123",
        "student123",
        "student@123",
        "collegeconnect",
        "changeme123",
        "default123",
        "test123456",
        "secret1234",
        "monkey12345",
        "dragon1234",
    ]
)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-ish time even for unknown users: always runs one Argon2 verification."""
    try:
        return _hasher.verify(password_hash or _dummy_hash(), password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def validate_new_password(password: str, *, avoid: tuple[str | None, ...] = (), field: str = "new_password") -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AppError(422, f"Use at least {MIN_PASSWORD_LENGTH} characters.", "weak_password", field)
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AppError(422, f"Use at most {MAX_PASSWORD_LENGTH} characters.", "weak_password", field)
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or len(set(lowered)) < 4:
        raise AppError(422, "This password is too common. Choose something harder to guess.", "weak_password", field)
    # Each part of the name, the email username and the PRN: "Meera Joshi" blocks "meera" and "joshi".
    parts = {p for value in avoid if value for p in re.split(r"[\s@._-]+", value.lower()) if len(p) >= 4}
    if any(p in lowered for p in parts):
        raise AppError(422, "Don't use your name, email or PRN in your password.", "weak_password", field)


def new_token() -> str:
    """A random token for sessions, reset links and setup (256 bits)."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """Only hashes of tokens are stored, so a database leak doesn't reveal usable tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i


def temporary_password() -> str:
    """Easy to read aloud or print on an admission slip, e.g. 'k7mr-x4tq-9bhn'."""
    groups = ["".join(secrets.choice(_TEMP_ALPHABET) for _ in range(4)) for _ in range(3)]
    return "-".join(groups)


def _fernet() -> Fernet:
    if not settings.app_secret_key:
        raise AppError(503, "Server is missing APP_SECRET_KEY; 2-step verification is unavailable.")
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.app_secret_key.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as e:
        raise AppError(500, "Stored secret could not be decrypted (APP_SECRET_KEY changed?).") from e
