"""Domain entity: Event (audit log entry)."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class EventType(str, Enum):
    """Enumeration of all auditable event types."""

    USER_LOGIN = "user_login"
    TOKEN_RENEWAL = "token_renewal"
    CSV_UPLOAD = "csv_upload"
    CSV_VALIDATION = "csv_validation"
    DOC_UPLOAD = "doc_upload"
    AI_CLASSIFICATION = "ai_classification"
    AI_EXTRACTION = "ai_extraction"
    EVENT_EXPORT = "event_export"
    ERROR = "error"


@dataclass
class Event:
    """An immutable audit-log entry.

    Attributes:
        id: Unique identifier (UUID v4).
        event_type: Category of the action that was performed.
        description: Human-readable summary of what happened.
        metadata: Arbitrary key-value payload for structured context.
        user_id: ID of the user who triggered the event; ``None`` for system events.
        created_at: UTC timestamp when the event was recorded.
    """

    id: UUID
    event_type: EventType
    description: str
    metadata: dict
    user_id: UUID | None
    created_at: datetime
