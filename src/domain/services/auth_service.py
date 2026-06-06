"""Domain service: AuthService — user authentication and JWT management."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext

from ..exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from ..ports.user_repository import IUserRepository


class AuthService:
    """Handles user authentication and JWT token management.

    Uses RS256 asymmetric signing so the public key can be distributed
    to any service that needs to verify tokens without exposing the
    private key.

    Args:
        user_repo: Repository for user lookup and persistence.
        settings: Application settings instance (provides JWT keys and expiry).
    """

    def __init__(self, user_repo: IUserRepository, settings) -> None:
        self._user_repo = user_repo
        self._settings = settings
        self._pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> str:
        """Authenticate a user and return a signed JWT.

        Looks up the user by username, verifies the plaintext password
        against the stored bcrypt hash, and issues a fresh token on success.

        Args:
            username: The user's login name.
            password: The plaintext password to verify.

        Returns:
            A signed JWT string with claims: ``sub``, ``rol``, ``iat``, ``exp``, ``jti``.

        Raises:
            AuthenticationError: If the username does not exist, the user is
                inactive, or the password does not match.
        """
        user = self._user_repo.find_by_username(username)
        if not user or not user.is_active:
            raise AuthenticationError("Invalid credentials")
        if not self._pwd_context.verify(password, user.password_hash):
            raise AuthenticationError("Invalid credentials")
        return self._create_token(str(user.id), user.rol.value)

    def refresh_token(self, token: str) -> str:
        """Issue a new JWT if the current token is still valid (not yet expired).

        Decodes the existing token to verify its signature and extract its
        subject claims, then issues a fresh token with a new expiry window.

        Args:
            token: The current JWT string to refresh.

        Returns:
            A new signed JWT with a fresh expiration timestamp.

        Raises:
            TokenExpiredError: If the token has already expired.
            InvalidTokenError: If the token signature or claims are invalid.
        """
        try:
            payload = jwt.decode(
                token,
                self._settings.JWT_PUBLIC_KEY,
                algorithms=[self._settings.JWT_ALGORITHM],
            )
        except ExpiredSignatureError as exc:
            raise TokenExpiredError(str(exc)) from exc
        except JWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        user_id = str(payload.get("id_usuario") or payload.get("sub") or "")
        if not user_id:
            raise InvalidTokenError("Token missing user identifier claim")

        return self._create_token(user_id, payload["rol"])

    def verify_token(self, token: str) -> dict:
        """Decode and validate a JWT, returning its payload.

        Args:
            token: JWT string to verify.

        Returns:
            The decoded payload dictionary (all registered + custom claims).

        Raises:
            InvalidTokenError: If the token is expired, has an invalid signature,
                or contains malformed claims.
        """
        try:
            return jwt.decode(
                token,
                self._settings.JWT_PUBLIC_KEY,
                algorithms=[self._settings.JWT_ALGORITHM],
            )
        except JWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password using bcrypt.

        Args:
            password: Plaintext password to hash.

        Returns:
            A bcrypt hash string suitable for storage.
        """
        return self._pwd_context.hash(password)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_token(self, user_id: str, rol: str) -> str:
        """Build and sign a JWT with the configured RS256 private key.

        Args:
            user_id: String representation of the user's UUID (``sub`` claim).
            rol: User role string (custom ``rol`` claim).

        Returns:
            A signed JWT string.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "id_usuario": user_id,
            "rol": rol,
            "iat": now,
            "exp": now + timedelta(minutes=self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
            "jti": str(uuid4()),
        }
        return jwt.encode(
            payload,
            self._settings.JWT_PRIVATE_KEY,
            algorithm=self._settings.JWT_ALGORITHM,
        )
