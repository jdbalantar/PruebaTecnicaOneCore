"""Port: IEventRepository — abstract event/audit-log persistence interface.

Also defines the EventFilters and EventPage value objects that are shared
between the port and the EventService.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from ..models.event import Event, EventType


@dataclass
class EventFilters:
    """Criteria for querying or exporting events.

    All fields are optional; omitted fields are not applied as filters.

    Attributes:
        event_type: Restrict results to a single event type.
        description_contains: Case-insensitive substring match on the description.
        date_from: Inclusive lower bound on ``created_at`` (UTC).
        date_to: Inclusive upper bound on ``created_at`` (UTC).
        page: 1-indexed page number for paginated queries.
        page_size: Maximum number of items per page.
    """

    event_type: EventType | None = None
    description_contains: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = 1
    page_size: int = 50


@dataclass
class EventPage:
    """A single page of query results from the event repository.

    Attributes:
        items: Events on the current page.
        total: Total number of matching events across all pages.
        page: Current 1-indexed page number.
        page_size: Number of items per page used for this query.
    """

    items: list[Event]
    total: int
    page: int
    page_size: int


class IEventRepository(ABC):
    """Abstract repository for audit-event persistence."""

    @abstractmethod
    def log_event(self, event: Event) -> Event:
        """Persist a new audit event and return the saved entity.

        Args:
            event: Fully populated Event to persist.

        Returns:
            The persisted Event (DB-assigned fields populated).
        """
        ...

    @abstractmethod
    def get_events(self, filters: EventFilters) -> EventPage:
        """Return a paginated, filtered page of audit events.

        Args:
            filters: Query parameters including pagination and filter criteria.

        Returns:
            An EventPage containing the matching items and pagination metadata.
        """
        ...

    @abstractmethod
    def get_events_for_export(self, filters: EventFilters) -> list[Event]:
        """Return all matching events (unpaginated) for bulk export.

        Args:
            filters: Filter criteria to apply (pagination fields are ignored).

        Returns:
            A list of all matching Event entities ordered by ``created_at``.
        """
        ...
