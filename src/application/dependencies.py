"""FastAPI dependency functions for authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.domain.exceptions import InvalidTokenError
from src.domain.services.auth_service import AuthService
from src.infrastructure.di import get_auth_service

security = HTTPBearer()


def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Validates JWT and returns its payload (sub, rol).

    Args:
        credentials: Bearer token extracted from the Authorization header.
        auth_service: AuthService instance injected by FastAPI.

    Returns:
        Decoded JWT payload dict containing at least ``sub`` and ``rol``.

    Raises:
        HTTPException: 401 if the token is invalid or malformed.
    """
    try:
        return auth_service.verify_token(credentials.credentials)
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


def require_role(*roles: str):
    """Returns a dependency that enforces one of the given roles.

    Args:
        *roles: Accepted role strings (e.g. ``"admin"``, ``"uploader"``).

    Returns:
        A FastAPI dependency callable that validates the caller's role.

    Raises:
        HTTPException: 403 if the authenticated user's role is not in *roles*.
    """

    def _checker(payload: dict = Depends(get_current_user_payload)) -> dict:
        if payload.get("rol") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return payload

    return _checker
