"""SQLAlchemy synchronous engine and session factory.

Provides:
- ``engine`` — a configured SQLAlchemy Engine for SQL Server via pyodbc.
- ``SessionLocal`` — a sessionmaker factory for request-scoped sessions.
- ``get_db()`` — FastAPI dependency that yields a session and closes it on exit.
"""

from collections.abc import Generator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import Settings, get_settings


def get_db_url(settings: Settings) -> str:
    """Build a pyodbc connection URL from application settings.

    Args:
        settings: Populated Settings instance.

    Returns:
        A SQLAlchemy-compatible connection string for SQL Server.
    """
    user = quote_plus(settings.DB_USER)
    password = quote_plus(settings.DB_PASSWORD)
    driver = quote_plus(settings.DB_DRIVER)
    return (
        f"mssql+pyodbc://{user}:{password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        f"?driver={driver}"
    )


def _create_engine(settings: Settings):
    """Create and return a SQLAlchemy Engine configured for SQL Server.

    Args:
        settings: Populated Settings instance.
    """
    return create_engine(
        get_db_url(settings),
        # Pool settings suitable for a synchronous web application.
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=settings.APP_DEBUG,
    )


_settings = get_settings()
engine = _create_engine(_settings)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session.

    Yields a session scoped to the request and guarantees it is closed
    after the response is sent — even if an exception is raised.

    Usage::

        @router.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(ItemModel).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
