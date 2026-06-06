"""Domain exception → HTTP response mappings for the FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.domain.exceptions import (
    AIServiceError,
    AuthenticationError,
    InvalidTokenError,
    NotFoundError,
    PermissionDeniedError,
    StorageError,
    ValidationError,
)
from src.application.schemas.result import fail


def register_exception_handlers(app: FastAPI) -> None:
    """Registers all domain exception handlers on the FastAPI app.

    Args:
        app: The FastAPI application instance to register handlers on.
    """

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=401,
            content=fail("auth_error", str(exc)),
        )

    @app.exception_handler(InvalidTokenError)
    async def invalid_token_handler(request: Request, exc: InvalidTokenError):
        return JSONResponse(
            status_code=401,
            content=fail("invalid_token", str(exc)),
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=404,
            content=fail("not_found", str(exc)),
        )

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
        return JSONResponse(
            status_code=403,
            content=fail("permission_denied", str(exc)),
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=422,
            content=fail("validation_error", str(exc)),
        )

    @app.exception_handler(StorageError)
    async def storage_error_handler(request: Request, exc: StorageError):
        return JSONResponse(
            status_code=503,
            content=fail("storage_unavailable", "Storage service unavailable"),
        )

    @app.exception_handler(AIServiceError)
    async def ai_error_handler(request: Request, exc: AIServiceError):
        return JSONResponse(
            status_code=503,
            content=fail(
                "ai_unavailable",
                "AI service unavailable",
                details={"reason": str(exc)},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=fail("http_error", str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=fail(
                "request_validation_error",
                "Request validation failed",
                details=exc.errors(),
            ),
        )
