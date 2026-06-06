"""Port: IUserRepository — abstract user persistence interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from ..models.user import User


class IUserRepository(ABC):
    """Abstract repository for User persistence.

    Implementations live in the infrastructure layer and are injected
    at application startup via the dependency-injection container.
    """

    @abstractmethod
    def find_by_username(self, username: str) -> User | None:
        """Return the User with the given username, or ``None`` if not found.

        Args:
            username: Exact username to look up.

        Returns:
            Matching User entity, or ``None``.
        """
        ...

    @abstractmethod
    def find_by_id(self, user_id: UUID) -> User | None:
        """Return the User with the given primary key, or ``None`` if not found.

        Args:
            user_id: UUID of the user to retrieve.

        Returns:
            Matching User entity, or ``None``.
        """
        ...

    @abstractmethod
    def create(self, user: User) -> User:
        """Persist a new User and return the saved entity.

        Args:
            user: Fully populated User dataclass to persist.

        Returns:
            The persisted User (may have DB-assigned fields populated).
        """
        ...
