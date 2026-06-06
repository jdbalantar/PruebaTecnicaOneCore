"""Web router — server-side rendered pages and HTMX partials."""

import dataclasses
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates

from src.domain.models.event import EventType
from src.domain.ports.event_repository import EventFilters
from src.domain.services.document_analysis_service import DocumentAnalysisService
from src.domain.services.event_service import EventService
from src.infrastructure.di import get_document_analysis_service, get_event_service

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="src/web/templates")

_optional_bearer = HTTPBearer(auto_error=False)

_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Redirect root to the login page."""
    return RedirectResponse(url="/login")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/documents", response_class=HTMLResponse)
def document_analysis_page(request: Request):
    """Render the document analysis page."""
    return templates.TemplateResponse("document_analysis.html", {"request": request})


@router.get("/events", response_class=HTMLResponse)
def event_history_page(request: Request):
    """Render the event history page."""
    return templates.TemplateResponse(
        "event_history.html",
        {
            "request": request,
            "event_types": [e.value for e in EventType],
        },
    )


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@router.get("/partials/events-table", response_class=HTMLResponse)
def events_table_partial(
    request: Request,
    event_type: Optional[str] = None,
    description: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    event_service: EventService = Depends(get_event_service),
):
    """Return an HTML partial with filtered event table rows.

    Accepts the same query parameters as ``GET /api/v1/events`` so the filter
    form can target this endpoint directly via HTMX.
    """
    parsed_event_type: Optional[EventType] = None
    if event_type:
        try:
            parsed_event_type = EventType(event_type)
        except ValueError:
            pass

    parsed_date_from: Optional[datetime] = None
    if date_from:
        try:
            parsed_date_from = datetime.fromisoformat(date_from)
        except ValueError:
            pass

    parsed_date_to: Optional[datetime] = None
    if date_to:
        try:
            parsed_date_to = datetime.fromisoformat(date_to)
        except ValueError:
            pass

    filters = EventFilters(
        event_type=parsed_event_type,
        description_contains=description or None,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        page=max(1, page),
        page_size=max(1, min(page_size, 100)),
    )

    result = event_service.list_events(filters)

    return templates.TemplateResponse(
        "events_table.html",
        {
            "request": request,
            "events": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        },
    )


@router.post("/partials/document-analyze", response_class=HTMLResponse)
async def document_analyze_partial(
    request: Request,
    file: UploadFile = File(...),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
    doc_service: DocumentAnalysisService = Depends(get_document_analysis_service),
):
    """Analyse an uploaded document and return an HTML partial with the result.

    Accepts PDF / JPG / PNG uploads.  If an Authorization header is present the
    token is forwarded implicitly via the DI-wired service.  The endpoint is
    intentionally lenient about auth so the web UI degrades gracefully.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Tipo de archivo no soportado: {file.content_type}. "
                f"Formatos aceptados: PDF, JPEG, PNG."
            ),
        )

    file_bytes = await file.read()

    user_id: Optional[UUID] = None
    if credentials and credentials.credentials:
        from src.application.dependencies import get_current_user_payload
        from src.infrastructure.di import get_auth_service
        from src.infrastructure.db.session import get_db

        db_gen = get_db()
        db = next(db_gen)
        try:
            auth_service = get_auth_service(db)
            payload = auth_service.verify_token(credentials.credentials)
            user_claim = payload.get("id_usuario") or payload.get("sub")
            if user_claim:
                user_id = UUID(str(user_claim))
        except Exception:
            pass
        finally:
            try:
                db_gen.close()
            except StopIteration:
                pass

    result = doc_service.analyze(
        file_bytes=file_bytes,
        filename=file.filename or "upload",
        content_type=file.content_type,
        user_id=user_id,
    )

    extracted = None
    if result.extracted_data is not None:
        extracted = dataclasses.asdict(result.extracted_data)

    return templates.TemplateResponse(
        "document_result.html",
        {
            "request": request,
            "result": {
                "document_id": str(result.document_id),
                "doc_type": result.doc_type.value
                if hasattr(result.doc_type, "value")
                else str(result.doc_type),
                "confidence": result.confidence,
                "extracted_data": extracted,
                "ai_model": result.ai_model,
            },
        },
    )
