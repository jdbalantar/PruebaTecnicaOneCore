"""SQLAlchemy implementation of IEventRepository."""

from uuid import UUID

from sqlalchemy.orm import Session

from src.domain.models.event import Event, EventType
from src.domain.ports.event_repository import EventFilters, EventPage, IEventRepository
from src.infrastructure.db.models import EventModel


class EventRepository(IEventRepository):
    """Concrete SQLAlchemy-backed repository for audit-event persistence.

    Args:
        session: An active SQLAlchemy Session scoped to the current request.
    """

    def __init__(self, session: Session) -> None:
        """Initialise the repository with a database session.

        Args:
            session: SQLAlchemy Session for executing queries.
        """
        self._session = session

    def log_event(self, event: Event) -> Event:
        """Persist a new audit event record.

        Maps the domain ``created_at`` field to the ORM ``timestamp`` column
        and ``metadata`` to the ORM ``metadata_`` attribute.

        Args:
            event: Fully populated Event to persist.

        Returns:
            The persisted Event with DB-assigned defaults populated.
        """
        model = EventModel(
            id=event.id,
            event_type=(
                event.event_type.value
                if isinstance(event.event_type, EventType)
                else event.event_type
            ),
            description=event.description,
            metadata_=event.metadata or {},
            user_id=event.user_id,
            timestamp=event.created_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def get_events(self, filters: EventFilters) -> EventPage:
        """Return a paginated, filtered page of audit events.

        Applies all non-None filter criteria, counts the total matching rows,
        then fetches the requested page ordered by timestamp descending.

        Args:
            filters: Query criteria including pagination parameters.

        Returns:
            EventPage containing matching items and pagination metadata.
        """
        query = self._build_query(filters)
        total = query.count()
        offset = (filters.page - 1) * filters.page_size
        models = (
            query.order_by(EventModel.timestamp.desc())
            .offset(offset)
            .limit(filters.page_size)
            .all()
        )
        return EventPage(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=filters.page,
            page_size=filters.page_size,
        )

    def get_events_for_export(self, filters: EventFilters) -> list[Event]:
        """Return all matching audit events without pagination (for bulk export).

        Applies the same filter criteria as ``get_events`` but returns every
        matching row ordered by timestamp descending.

        Args:
            filters: Filter criteria to apply (pagination fields are ignored).

        Returns:
            List of all matching Event entities ordered by timestamp descending.
        """
        query = self._build_query(filters)
        models = query.order_by(EventModel.timestamp.desc()).all()
        return [self._to_domain(m) for m in models]

    def _build_query(self, filters: EventFilters):
        """Construct a SQLAlchemy query from the given EventFilters.

        Applies each filter criterion only when its value is not None.

        Args:
            filters: Filter criteria to translate into SQL predicates.

        Returns:
            A SQLAlchemy Query object with all applicable filters applied.
        """
        query = self._session.query(EventModel)

        if filters.event_type is not None:
            type_value = (
                filters.event_type.value
                if isinstance(filters.event_type, EventType)
                else filters.event_type
            )
            query = query.filter(EventModel.event_type == type_value)

        if filters.description_contains is not None:
            query = query.filter(
                EventModel.description.ilike(f"%{filters.description_contains}%")
            )

        if filters.date_from is not None:
            query = query.filter(EventModel.timestamp >= filters.date_from)

        if filters.date_to is not None:
            query = query.filter(EventModel.timestamp <= filters.date_to)

        return query

    def _to_domain(self, model: EventModel) -> Event:
        """Map an EventModel ORM instance to an Event domain entity.

        Maps ``timestamp`` → ``created_at`` and ``metadata_`` → ``metadata``.

        Args:
            model: The ORM model instance to map.

        Returns:
            An Event domain dataclass.
        """
        return Event(
            id=model.id,
            event_type=EventType(model.event_type),
            description=model.description,
            metadata=model.metadata_ or {},
            user_id=model.user_id,
            created_at=model.timestamp,
        )
