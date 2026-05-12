"""User creation service with bcrypt password hashing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt


class DuplicateUserError(ValueError):
    """Raised when an email is already registered."""


@dataclass(frozen=True, slots=True)
class UserRecord:
    """Internal user record with hashed password."""

    id: str
    email: str
    password_hash: str
    created_at: str

    def to_public(self) -> dict[str, str]:
        """Return the public user payload."""
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at,
        }


class UserService:
    """In-memory user store for API-level registration."""

    def __init__(self) -> None:
        self._users_by_email: dict[str, UserRecord] = {}

    def create_user(self, email: str, password: str) -> UserRecord:
        """Create and store a user with a bcrypt password hash."""
        normalized_email = email.strip().lower()
        if normalized_email in self._users_by_email:
            raise DuplicateUserError(
                f"User with email {normalized_email!r} already exists",
            )
        user = UserRecord(
            id=str(uuid4()),
            email=normalized_email,
            password_hash=_hash_password(password),
            created_at=_utc_now(),
        )
        self._users_by_email[normalized_email] = user
        return user

    def get_by_email(self, email: str) -> UserRecord | None:
        """Return a stored user by normalized email."""
        return self._users_by_email.get(email.strip().lower())


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def _utc_now() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
