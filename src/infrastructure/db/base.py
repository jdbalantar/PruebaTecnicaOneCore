"""SQLAlchemy declarative base shared across all ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models in PruebaTecnica.

    All models inherit from this class to share the same metadata registry,
    enabling Alembic autogenerate and consistent table management.
    """
