"""Auth router — login and token-refresh endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.application.dependencies import get_current_user_payload
from src.application.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from src.application.schemas.result import Result, ok
from src.domain.services.auth_service import AuthService
from src.infrastructure.di import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Result[TokenResponse]:
    """Authenticates a user and returns a JWT access token.

    Args:
        request: Username and password credentials.
        auth_service: AuthService injected by FastAPI.

    Returns:
        TokenResponse containing the signed JWT and its expiry.

    Raises:
        HTTPException: 401 if credentials are invalid or the account is inactive.
    """
    token = auth_service.login(request.username, request.password)
    return ok(TokenResponse(access_token=token))


@router.post("/refresh")
def refresh_token(
    request: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Result[TokenResponse]:
    """Refreshes a JWT token. The token must not be expired.

    Args:
        request: The current valid JWT to refresh.
        auth_service: AuthService injected by FastAPI.

    Returns:
        TokenResponse containing a new signed JWT.

    Raises:
        HTTPException: 401 if the supplied token is invalid or expired.
    """
    new_token = auth_service.refresh_token(request.token)
    return ok(TokenResponse(access_token=new_token))
