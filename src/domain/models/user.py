"""Domain entity: User."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class UserRole(str, Enum):
    """Allowed roles for a user account."""

    ADMIN = "admin"
    UPLOADER = "uploader"
    VIEWER = "viewer"


@dataclass
class User:
    """Core user entity.

    Attributes:
        id: Unique identifier (UUID v4).
        username: Human-readable login name (max 100 chars).
        password_hash: bcrypt-hashed password; may be empty for anonymous users.
        rol: Role governing API permissions.
        created_at: UTC timestamp when the account was created.
        is_active: Whether the account is allowed to authenticate.
    """

    id: UUID
    username: str
    password_hash: str
    rol: UserRole
    created_at: datetime
    is_active: bool = True
