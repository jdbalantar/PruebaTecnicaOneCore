"""Pydantic schemas for authentication endpoints."""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Request body for the login endpoint."""

    username: str
    password: str


class TokenResponse(BaseModel):
    """Response body containing a JWT access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # seconds


class RefreshRequest(BaseModel):
    """Request body for the token-refresh endpoint."""

    token: str
