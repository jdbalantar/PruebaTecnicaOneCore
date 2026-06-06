"""SQLAlchemy implementation of IUserRepository."""

from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.models.user import User, UserRole
from src.domain.ports.user_repository import IUserRepository
from src.infrastructure.db.models import UserModel


class UserRepository(IUserRepository):
    """Concrete SQLAlchemy-backed repository for User persistence.

    Args:
        session: An active SQLAlchemy Session scoped to the current request.
    """

    def __init__(self, session: Session) -> None:
        """Initialise the repository with a database session.

        Args:
            session: SQLAlchemy Session for executing queries.
        """
        self._session = session

    def find_by_username(self, username: str) -> User | None:
        """Query the users table by exact username match.

        Args:
            username: Exact username to search for.

        Returns:
            Matching User entity, or None if not found.
        """
        model = (
            self._session.query(UserModel)
            .filter(UserModel.username == username)
            .first()
        )
        if model is None:
            return None
        return self._to_domain(model)

    def find_by_id(self, user_id: UUID) -> User | None:
        """Query the users table by primary key.

        Args:
            user_id: UUID of the user to retrieve.

        Returns:
            Matching User entity, or None if not found.
        """
        model = self._session.get(UserModel, user_id)
        if model is None:
            return None
        return self._to_domain(model)

    def create(self, user: User) -> User:
        """Insert a new user record and return the persisted entity.

        Args:
            user: User dataclass to persist.

        Returns:
            The persisted User with any DB-assigned defaults populated.
        """
        model = UserModel(
            id_usuario=user.id,
            username=user.username,
            password_hash=user.password_hash,
            rol=user.rol.value if isinstance(user.rol, UserRole) else user.rol,
            created_at=user.created_at,
            is_active=user.is_active,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def _to_domain(self, model: UserModel) -> User:
        """Map a UserModel ORM instance to a User domain entity.

        Args:
            model: The ORM model instance to map.

        Returns:
            A User domain dataclass populated from the model's fields.
        """
        return User(
            id=model.id_usuario,
            username=model.username or "",
            password_hash=model.password_hash or "",
            rol=UserRole(model.rol),
            created_at=model.created_at,
            is_active=model.is_active,
        )
