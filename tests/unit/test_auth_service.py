"""Unit tests for AuthService — login, refresh, and token verification."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from jose import jwt as jose_jwt
from passlib.context import CryptContext

from src.domain.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError
from src.domain.models.user import User, UserRole
from src.domain.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
HASHED_PASSWORD = _pwd.hash("password123")

_USER_ID = uuid4()

ACTIVE_USER = User(
    id=_USER_ID,
    username="testuser",
    password_hash=HASHED_PASSWORD,
    rol=UserRole.UPLOADER,
    created_at=datetime.now(timezone.utc),
    is_active=True,
)

INACTIVE_USER = User(
    id=uuid4(),
    username="inactive",
    password_hash=HASHED_PASSWORD,
    rol=UserRole.VIEWER,
    created_at=datetime.now(timezone.utc),
    is_active=False,
)


def _make_service(mock_user_repo, mock_settings) -> AuthService:
    """Instantiate AuthService with injected mocks."""
    return AuthService(mock_user_repo, mock_settings)


def _decode(token: str, settings) -> dict:
    """Decode a JWT using the test settings (HS256 + shared secret)."""
    return jose_jwt.decode(
        token,
        settings.JWT_PUBLIC_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# ---------------------------------------------------------------------------
# Tests: Login
# ---------------------------------------------------------------------------


class TestAuthServiceLogin:
    """Tests for AuthService.login."""

    @pytest.mark.parametrize(
        "username,password,user_stub",
        [
            ("", "password123", None),           # empty username → no user found
            ("testuser", "", ACTIVE_USER),        # user found but empty password
            ("unknown", "password123", None),     # user not found
            ("inactive", "password123", INACTIVE_USER),  # inactive account
        ],
    )
    def test_login_invalid_credentials(
        self, username, password, user_stub, mock_user_repo, mock_settings
    ):
        """Any credential failure must raise AuthenticationError."""
        mock_user_repo.find_by_username.return_value = user_stub
        service = _make_service(mock_user_repo, mock_settings)

        with pytest.raises(AuthenticationError):
            service.login(username, password)

    def test_login_success_returns_jwt(self, mock_user_repo, mock_settings):
        """Valid credentials must return a non-empty JWT string."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)

        token = service.login("testuser", "password123")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_login_jwt_contains_user_id_and_rol(self, mock_user_repo, mock_settings):
        """Issued JWT must embed the user's UUID as 'sub' and role as 'rol'."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)

        token = service.login("testuser", "password123")
        payload = _decode(token, mock_settings)

        assert payload["sub"] == str(ACTIVE_USER.id)
        assert payload["rol"] == UserRole.UPLOADER.value

    def test_login_jwt_expires_in_15_minutes(self, mock_user_repo, mock_settings):
        """Issued JWT expiry must be approximately 15 minutes from now."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)

        before = datetime.now(timezone.utc)
        token = service.login("testuser", "password123")
        after = datetime.now(timezone.utc)

        payload = _decode(token, mock_settings)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        assert exp >= before + timedelta(minutes=14, seconds=59)
        assert exp <= after + timedelta(minutes=15, seconds=1)

    def test_login_wrong_password_raises_auth_error(self, mock_user_repo, mock_settings):
        """Providing a wrong password for an active user must raise AuthenticationError."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)

        with pytest.raises(AuthenticationError):
            service.login("testuser", "wrong-password")

    def test_login_inactive_user_raises_auth_error(self, mock_user_repo, mock_settings):
        """Attempting to log in as an inactive user must raise AuthenticationError."""
        mock_user_repo.find_by_username.return_value = INACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)

        with pytest.raises(AuthenticationError):
            service.login("inactive", "password123")

    def test_login_jwt_contains_jti_claim(self, mock_user_repo, mock_settings):
        """Issued JWT must contain a unique 'jti' claim for replay prevention."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)

        token = service.login("testuser", "password123")
        payload = _decode(token, mock_settings)

        assert "jti" in payload
        assert len(payload["jti"]) > 0

    def test_login_two_tokens_have_different_jtis(self, mock_user_repo, mock_settings):
        """Each login call must produce a token with a distinct 'jti'."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)

        token_a = service.login("testuser", "password123")
        token_b = service.login("testuser", "password123")

        jti_a = _decode(token_a, mock_settings)["jti"]
        jti_b = _decode(token_b, mock_settings)["jti"]

        assert jti_a != jti_b


# ---------------------------------------------------------------------------
# Tests: RefreshToken
# ---------------------------------------------------------------------------


class TestAuthServiceRefreshToken:
    """Tests for AuthService.refresh_token."""

    def test_refresh_valid_token_returns_new_token(self, mock_user_repo, mock_settings):
        """A valid, non-expired token must produce a new JWT string."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)
        original = service.login("testuser", "password123")

        new_token = service.refresh_token(original)

        assert isinstance(new_token, str)
        assert new_token != original

    def test_refresh_expired_token_raises_token_expired_error(
        self, mock_user_repo, mock_settings
    ):
        """An expired token must raise TokenExpiredError."""
        service = _make_service(mock_user_repo, mock_settings)
        expired = jose_jwt.encode(
            {
                "sub": str(uuid4()),
                "rol": "uploader",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            mock_settings.JWT_PRIVATE_KEY,
            algorithm=mock_settings.JWT_ALGORITHM,
        )

        with pytest.raises(TokenExpiredError):
            service.refresh_token(expired)

    def test_refresh_invalid_signature_raises_invalid_token(
        self, mock_user_repo, mock_settings
    ):
        """A token signed with the wrong key must raise InvalidTokenError."""
        service = _make_service(mock_user_repo, mock_settings)
        bad_sig_token = jose_jwt.encode(
            {"sub": str(uuid4()), "rol": "uploader"},
            "totally-wrong-secret",
            algorithm="HS256",
        )

        with pytest.raises(InvalidTokenError):
            service.refresh_token(bad_sig_token)

    def test_refresh_malformed_token_raises_invalid_token(
        self, mock_user_repo, mock_settings
    ):
        """A non-JWT string must raise InvalidTokenError."""
        service = _make_service(mock_user_repo, mock_settings)

        with pytest.raises(InvalidTokenError):
            service.refresh_token("not.a.valid.jwt.string")

    def test_refresh_new_token_has_fresh_expiry(self, mock_user_repo, mock_settings):
        """The refreshed token must have an expiry later than the original."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)
        original = service.login("testuser", "password123")
        original_exp = _decode(original, mock_settings)["exp"]

        new_token = service.refresh_token(original)
        new_exp = _decode(new_token, mock_settings)["exp"]

        assert new_exp >= original_exp


# ---------------------------------------------------------------------------
# Tests: VerifyToken
# ---------------------------------------------------------------------------


class TestAuthServiceVerifyToken:
    """Tests for AuthService.verify_token."""

    def test_verify_valid_token_returns_payload(self, mock_user_repo, mock_settings):
        """A valid token must be decoded and return a dict with expected claims."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)
        token = service.login("testuser", "password123")

        payload = service.verify_token(token)

        assert payload["sub"] == str(ACTIVE_USER.id)
        assert payload["rol"] == UserRole.UPLOADER.value
        assert "exp" in payload
        assert "jti" in payload

    def test_verify_tampered_token_raises_invalid_token(
        self, mock_user_repo, mock_settings
    ):
        """A token with a modified signature must raise InvalidTokenError."""
        mock_user_repo.find_by_username.return_value = ACTIVE_USER
        service = _make_service(mock_user_repo, mock_settings)
        token = service.login("testuser", "password123")
        # Flip the last character of the signature segment
        parts = token.split(".")
        tampered = ".".join(parts[:2]) + "." + parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")

        with pytest.raises(InvalidTokenError):
            service.verify_token(tampered)

    def test_verify_expired_token_raises_invalid_token(
        self, mock_user_repo, mock_settings
    ):
        """An expired token must raise InvalidTokenError from verify_token."""
        service = _make_service(mock_user_repo, mock_settings)
        expired = jose_jwt.encode(
            {
                "sub": str(uuid4()),
                "rol": "uploader",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            mock_settings.JWT_PRIVATE_KEY,
            algorithm=mock_settings.JWT_ALGORITHM,
        )

        with pytest.raises(InvalidTokenError):
            service.verify_token(expired)
