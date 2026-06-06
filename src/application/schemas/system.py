"""Pydantic schemas for infrastructure health endpoints."""

from pydantic import BaseModel


class ServiceHealthResponse(BaseModel):
    """Health status for an individual service dependency."""

    status: str
    detail: str


class SystemHealthResponse(BaseModel):
    """Health summary for API + infrastructure dependencies."""

    status: str
    timestamp: str
    services: dict[str, ServiceHealthResponse]
