"""Integration tests for auth, files, and events API endpoints using FastAPI TestClient.

All infrastructure calls (DB, S3, AI) are replaced via app.dependency_overrides so
no external services are required to run these tests.
"""

import os
import sys
from unittest.mock import MagicMock

# ---- Stubs: must be set BEFORE any src.* import ----
# session.py calls create_engine() at module level which requires pyodbc.
# Stub it entirely; get_db is overridden via dependency_overrides in every test.
sys.modules.setdefault("pyodbc", MagicMock(version="4.0.30"))
_session_stub = MagicMock()
_session_stub.get_db = MagicMock()
sys.modules["src.infrastructure.db.session"] = _session_stub

# 2. Set required env vars to satisfy pydantic-settings validation.
_TEST_ENV = {
    "SECRET_KEY": "integration-test-secret",
    "JWT_ALGORITHM": "HS256",
    "JWT_PRIVATE_KEY": "integration-test-key",
    "JWT_PUBLIC_KEY": "integration-test-key",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
}
for _k, _v in _TEST_ENV.items():
    os.environ.setdefault(_k, _v)

# 3. Clear the lru_cache so Settings is rebuilt from the env vars above.
from src.config.settings import get_settings
get_settings.cache_clear()

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app
from src.infrastructure.di import (
    get_auth_service,
    get_event_service,
    get_file_upload_service,
)
from src.domain.exceptions import AuthenticationError, InvalidTokenError
from src.domain.models.event import EventType
from src.domain.ports.event_repository import EventPage, EventFilters

# ---------------------------------------------------------------------------
# Module-level TestClient (shared across all test classes)
# ---------------------------------------------------------------------------

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixture: clear dependency overrides between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Reset app.dependency_overrides after every test to prevent leakage."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_auth_service(login_return=None, refresh_return=None, verify_return=None):
    """Build a MagicMock that mimics AuthService for dependency injection."""
    svc = MagicMock()
    if login_return is not None:
        svc.login.return_value = login_return
    if refresh_return is not None:
        svc.refresh_token.return_value = refresh_return
    if verify_return is not None:
        svc.verify_token.return_value = verify_return
    return svc


def _override_auth(service) -> None:
    """Register an auth service override on the FastAPI app."""
    app.dependency_overrides[get_auth_service] = lambda: service


# ---------------------------------------------------------------------------
# Tests: /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login."""

    def test_login_returns_200_with_valid_credentials(self):
        """Valid credentials must yield HTTP 200."""
        svc = _mock_auth_service(login_return="fake.jwt.token")
        _override_auth(svc)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "secret"},
        )

        assert response.status_code == 200

    def test_login_returns_401_with_invalid_credentials(self):
        """Invalid credentials (AuthenticationError) must yield HTTP 401."""
        svc = MagicMock()
        svc.login.side_effect = AuthenticationError("Invalid credentials")
        _override_auth(svc)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "bad", "password": "wrong"},
        )

        assert response.status_code == 401

    def test_login_response_contains_access_token(self):
        """A successful login response body must include the 'access_token' field."""
        svc = _mock_auth_service(login_return="my.signed.jwt")
        _override_auth(svc)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "user", "password": "pass"},
        )

        data = response.json()
        assert "access_token" in data
        assert data["access_token"] == "my.signed.jwt"

    def test_login_response_contains_token_type_bearer(self):
        """A successful login response must set token_type to 'bearer'."""
        svc = _mock_auth_service(login_return="a.b.c")
        _override_auth(svc)

        response = client.post(
            "/api/v1/auth/login",
            json={"username": "user", "password": "pass"},
        )

        assert response.json()["token_type"] == "bearer"

    def test_login_missing_fields_returns_422(self):
        """A request body missing required fields must yield HTTP 422 (validation)."""
        response = client.post("/api/v1/auth/login", json={})

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: /api/v1/auth/refresh
# ---------------------------------------------------------------------------


class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh."""

    def test_refresh_returns_200_with_valid_token(self):
        """A valid, non-expired token must yield HTTP 200 with a new access_token."""
        svc = _mock_auth_service(refresh_return="new.jwt.token")
        _override_auth(svc)

        response = client.post(
            "/api/v1/auth/refresh",
            json={"token": "valid.current.token"},
        )

        assert response.status_code == 200
        assert response.json()["access_token"] == "new.jwt.token"

    def test_refresh_returns_401_with_expired_token(self):
        """An expired/invalid token must yield HTTP 401."""
        svc = MagicMock()
        svc.refresh_token.side_effect = InvalidTokenError("Token expired or invalid")
        _override_auth(svc)

        response = client.post(
            "/api/v1/auth/refresh",
            json={"token": "expired.jwt.token"},
        )

        assert response.status_code == 401

    def test_refresh_missing_token_field_returns_422(self):
        """An empty request body must yield HTTP 422."""
        response = client.post("/api/v1/auth/refresh", json={})

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: /api/v1/files/upload
# ---------------------------------------------------------------------------


class TestFilesEndpoint:
    """Tests for POST /api/v1/files/upload."""

    def test_upload_csv_returns_401_without_token(self):
        """A request without an Authorization header must be rejected with HTTP 401.

        Starlette 1.x changed HTTPBearer to return 401 (previously 403).
        """
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("data.csv", b"col\nval", "text/csv")},
        )

        assert response.status_code == 401

    def test_upload_csv_returns_403_with_wrong_role(self):
        """A user with the 'viewer' role must be rejected with HTTP 403."""
        auth_svc = MagicMock()
        auth_svc.verify_token.return_value = {"sub": str(uuid4()), "rol": "viewer"}
        _override_auth(auth_svc)

        response = client.post(
            "/api/v1/files/upload",
            headers={"Authorization": "Bearer sometoken"},
            files={"file": ("data.csv", b"col\nval", "text/csv")},
            data={"validation_mode": "lenient"},
        )

        assert response.status_code == 403

    def test_upload_csv_returns_400_for_non_csv_file(self):
        """Uploading a non-.csv file (e.g. .txt) must yield HTTP 400."""
        auth_svc = MagicMock()
        auth_svc.verify_token.return_value = {"sub": str(uuid4()), "rol": "uploader"}
        _override_auth(auth_svc)
        # Override the upload service so the handler runs (bypasses real DB/S3 init)
        app.dependency_overrides[get_file_upload_service] = lambda: MagicMock()

        response = client.post(
            "/api/v1/files/upload",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("report.txt", b"content", "text/plain")},
            data={"validation_mode": "lenient"},
        )

        assert response.status_code == 400

    def test_upload_csv_returns_200_with_valid_payload(self):
        """An uploader with a valid CSV must receive HTTP 200."""
        user_id = uuid4()
        auth_svc = MagicMock()
        auth_svc.verify_token.return_value = {"sub": str(user_id), "rol": "uploader"}
        _override_auth(auth_svc)

        # Mock the file upload service
        from src.domain.models.csv_upload import UploadResult
        upload_result = UploadResult(
            upload_id=uuid4(),
            filename="data.csv",
            s3_key="csv/key",
            total_rows=1,
            valid_rows=1,
            error_rows=0,
            validations=[],
            status="completed",
        )
        mock_upload_svc = MagicMock()
        mock_upload_svc.upload_and_validate.return_value = upload_result
        app.dependency_overrides[get_file_upload_service] = lambda: mock_upload_svc

        csv_bytes = b"col1,col2\nval1,val2\n"
        response = client.post(
            "/api/v1/files/upload",
            headers={"Authorization": "Bearer tok"},
            files={"file": ("data.csv", csv_bytes, "text/csv")},
            data={"validation_mode": "lenient"},
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: /api/v1/events
# ---------------------------------------------------------------------------


class TestEventsEndpoint:
    """Tests for GET /api/v1/events."""

    def test_list_events_returns_401_without_token(self):
        """A request without an Authorization header must be rejected with HTTP 401.

        Starlette 1.x changed HTTPBearer to return 401 (previously 403).
        """
        response = client.get("/api/v1/events")

        assert response.status_code == 401

    def test_list_events_returns_200_with_valid_token(self):
        """Any authenticated user must be able to list events (HTTP 200)."""
        auth_svc = MagicMock()
        auth_svc.verify_token.return_value = {"sub": str(uuid4()), "rol": "viewer"}
        _override_auth(auth_svc)

        mock_event_svc = MagicMock()
        mock_event_svc.list_events.return_value = EventPage(
            items=[], total=0, page=1, page_size=50
        )
        app.dependency_overrides[get_event_service] = lambda: mock_event_svc

        response = client.get(
            "/api/v1/events",
            headers={"Authorization": "Bearer tok"},
        )

        assert response.status_code == 200

    def test_list_events_returns_401_with_invalid_token(self):
        """An invalid JWT must be rejected with HTTP 401."""
        auth_svc = MagicMock()
        auth_svc.verify_token.side_effect = InvalidTokenError("bad token")
        _override_auth(auth_svc)

        response = client.get(
            "/api/v1/events",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401
