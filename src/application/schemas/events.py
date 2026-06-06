"""Pydantic schemas for event/audit-log endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EventResponse(BaseModel):
    """A single audit-log entry returned by the API."""

    id: str
    event_type: str
    description: str
    metadata: dict[str, Any]
    user_id: str | None
    created_at: datetime


class EventPageResponse(BaseModel):
    """Paginated list of audit-log entries."""

    items: list[EventResponse]
    total: int
    page: int
    page_size: int
