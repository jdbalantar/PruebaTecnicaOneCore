"""Events router — paginated listing and Excel export of audit-log entries."""

import io
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from src.application.dependencies import get_current_user_payload
from src.application.schemas.events import EventPageResponse, EventResponse
from src.application.schemas.result import Result, ok
from src.domain.models.event import EventType
from src.domain.ports.event_repository import EventFilters
from src.domain.services.event_service import EventService
from src.infrastructure.di import get_event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def list_events(
    payload: Annotated[dict, Depends(get_current_user_payload)],
    service: Annotated[EventService, Depends(get_event_service)],
    event_type: Annotated[Optional[str], Query(description="Filter by EventType value")] = None,
    description: Annotated[Optional[str], Query(description="Partial text match on description")] = None,
    date_from: Annotated[
        Optional[datetime],
        Query(description="Inclusive lower bound on created_at (ISO 8601)"),
    ] = None,
    date_to: Annotated[
        Optional[datetime],
        Query(description="Inclusive upper bound on created_at (ISO 8601)"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, description="Results per page (max 200)")] = 50,
) -> Result[EventPageResponse]:
    """Returns a paginated list of audit events with optional filters.

    Requires: valid JWT (any role).

    Args:
        event_type: Restrict results to this EventType value.
        description: Case-insensitive substring match on the event description.
        date_from: Inclusive start of the date range (UTC, ISO 8601).
        date_to: Inclusive end of the date range (UTC, ISO 8601).
        page: 1-indexed page number (default 1).
        page_size: Number of results per page, max 200 (default 50).
        payload: Decoded JWT payload — injected by ``get_current_user_payload``.
        service: EventService injected by FastAPI.

    Returns:
        EventPageResponse with items, total count, current page and page size.
    """
    et = EventType(event_type) if event_type else None
    filters = EventFilters(
        event_type=et,
        description_contains=description,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    result = service.list_events(filters)
    return ok(
        EventPageResponse(
            items=[
                EventResponse(
                    id=str(e.id),
                    event_type=e.event_type.value,
                    description=e.description,
                    metadata=e.metadata,
                    user_id=str(e.user_id) if e.user_id else None,
                    created_at=e.created_at,
                )
                for e in result.items
            ],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
        )
    )


@router.get("/export")
def export_events(
    payload: Annotated[dict, Depends(get_current_user_payload)],
    service: Annotated[EventService, Depends(get_event_service)],
    event_type: Annotated[Optional[str], Query(description="Filter by EventType value")] = None,
    description: Annotated[Optional[str], Query(description="Partial text match on description")] = None,
    date_from: Annotated[
        Optional[datetime],
        Query(description="Inclusive lower bound on created_at (ISO 8601)"),
    ] = None,
    date_to: Annotated[
        Optional[datetime],
        Query(description="Inclusive upper bound on created_at (ISO 8601)"),
    ] = None,
) -> StreamingResponse:
    """Exports filtered events to an Excel (.xlsx) file.

    Requires: valid JWT (any role).

    Args:
        event_type: Restrict export to this EventType value.
        description: Case-insensitive substring match on the event description.
        date_from: Inclusive start of the date range (UTC, ISO 8601).
        date_to: Inclusive end of the date range (UTC, ISO 8601).
        payload: Decoded JWT payload — injected by ``get_current_user_payload``.
        service: EventService injected by FastAPI.

    Returns:
        StreamingResponse delivering the Excel file as an attachment.
    """
    et = EventType(event_type) if event_type else None
    filters = EventFilters(
        event_type=et,
        description_contains=description,
        date_from=date_from,
        date_to=date_to,
        page=1,
        page_size=100_000,  # no pagination for export
    )

    excel_bytes = service.export_to_excel(filters)

    date_suffix = ""
    if date_from and date_to:
        date_suffix = f"_{date_from.date()}_{date_to.date()}"

    filename = f"eventos{date_suffix}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
