"""FastAPI application factory for PruebaTecnica.

Entry point for the ASGI server.  Routers are imported conditionally so
the factory works during scaffolding before all route modules exist.
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.application.schemas.result import fail
from src.config.settings import get_settings

_settings = get_settings()
API_V1_PREFIX = "/api/v1"


# ---------------------------------------------------------------------------
# Middleware helpers
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every incoming request and response.

    The ID is added as the ``X-Request-ID`` header so it can be forwarded
    to downstream services and correlated in log aggregators.
    """

    async def dispatch(self, request: Request, call_next):
        """Process the request, inject a request ID, and forward the response."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log each request method, path, status code, and request ID."""

    async def dispatch(self, request: Request, call_next):
        """Log request/response details at INFO level."""
        import logging

        logger = logging.getLogger("prueba_tecnica.access")
        response = await call_next(request)
        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s → %d [req=%s]",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
        )
        return response


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: run startup logic, then yield, then shutdown."""
    import logging

    logging.basicConfig(level=logging.DEBUG if _settings.APP_DEBUG else logging.INFO)
    logging.getLogger("prueba_tecnica").info(
        "Starting %s (env=%s)", _settings.APP_NAME, _settings.APP_ENV
    )
    yield
    logging.getLogger("prueba_tecnica").info("Shutting down %s", _settings.APP_NAME)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Registers middleware, exception handlers, and API routers.  Routers
    are imported inside this function so that circular-import problems are
    avoided during the early scaffold phase.

    Returns:
        Fully configured ``FastAPI`` instance ready to be served by Uvicorn.
    """
    app = FastAPI(
        title="PruebaTecnica OneCore",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # --- Custom middleware (order: outer → inner) ---
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LoggingMiddleware)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tighten in production via settings
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Global exception handlers ---
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Return a JSON 500 for any unhandled exception."""
        import logging

        logging.getLogger("prueba_tecnica").exception(
            "Unhandled exception for %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500,
            content=fail("internal_server_error", "Internal server error"),
        )

    # --- Health check ---
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health() -> dict:
        """Return application health status.

        Returns:
            A dict with ``status`` and ``version`` keys.
        """
        return {"status": "ok", "version": "0.1.0"}

    # --- Domain exception handlers ---
    from src.application.exception_handlers import register_exception_handlers

    register_exception_handlers(app)

    # --- Static files ---
    from fastapi.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

    # --- API routers ---
    from src.application.api.v1.auth import router as auth_router
    from src.application.api.v1.documents import router as documents_router
    from src.application.api.v1.events import router as events_router
    from src.application.api.v1.files import router as files_router
    from src.application.api.v1.system import router as system_router

    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(files_router, prefix=API_V1_PREFIX)
    app.include_router(documents_router, prefix=API_V1_PREFIX)
    app.include_router(events_router, prefix=API_V1_PREFIX)
    app.include_router(system_router, prefix=API_V1_PREFIX)

    # --- Web router (server-side rendered pages) ---
    from src.web.router import router as web_router

    app.include_router(web_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=_settings.APP_HOST,
        port=_settings.APP_PORT,
        reload=_settings.APP_ENV == "development",
    )
