"""Generic API result envelope used by all JSON endpoints."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResultError(BaseModel):
    """Standardized error payload for API responses."""

    code: str
    message: str
    details: Any | None = None


class Result(BaseModel, Generic[T]):
    """Standard response envelope for success/error results."""

    success: bool
    data: T | None = None
    error: ResultError | None = None


def ok(data: T) -> Result[T]:
    """Build a successful result envelope."""
    return Result[T](success=True, data=data, error=None)


def fail(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    """Build an error result payload for HTTP error responses."""
    payload = Result[dict](
        success=False,
        data=None,
        error=ResultError(code=code, message=message, details=details),
    )
    return payload.model_dump(exclude_none=True)
