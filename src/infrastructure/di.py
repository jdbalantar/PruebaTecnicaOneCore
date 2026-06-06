"""Dependency injection container for the PruebaTecnica application.

Provides FastAPI dependency functions that wire together repository
implementations, infrastructure adapters, and domain services.
All functions rely on FastAPI's ``Depends`` mechanism so that a fresh
session-scoped DB session is injected per request.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from src.config import get_settings
from src.domain.services.auth_service import AuthService
from src.domain.services.document_analysis_service import DocumentAnalysisService
from src.domain.services.event_service import EventService
from src.domain.services.file_upload_service import FileUploadService
from src.infrastructure.ai.gemini_adapter import GeminiDocumentAdapter
from src.infrastructure.db.session import get_db
from src.infrastructure.repositories.csv_repository import CSVRepository
from src.infrastructure.repositories.document_repository import DocumentRepository
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.user_repository import UserRepository
from src.infrastructure.storage.s3_adapter import S3FileStorageAdapter


def _build_storage_adapters(settings) -> dict[str, S3FileStorageAdapter]:
    minio_endpoint = settings.MINIO_ENDPOINT_URL or settings.S3_ENDPOINT_URL
    minio_access_key = settings.MINIO_ACCESS_KEY_ID or settings.AWS_ACCESS_KEY_ID
    minio_secret_key = settings.MINIO_SECRET_ACCESS_KEY or settings.AWS_SECRET_ACCESS_KEY

    return {
        "minio": S3FileStorageAdapter(
            settings,
            endpoint_url=minio_endpoint,
            access_key_id=minio_access_key,
            secret_access_key=minio_secret_key,
        ),
        "localstack": S3FileStorageAdapter(
            settings,
            endpoint_url=settings.LOCALSTACK_ENDPOINT_URL,
            access_key_id=settings.LOCALSTACK_ACCESS_KEY_ID,
            secret_access_key=settings.LOCALSTACK_SECRET_ACCESS_KEY,
        ),
    }


def _build_document_ai_adapter(settings):
    provider = settings.AI_PROVIDER.strip().lower()
    if provider in ("", "gemini"):
        return GeminiDocumentAdapter(settings)

    raise ValueError(
        f"Unsupported AI_PROVIDER '{settings.AI_PROVIDER}'. Use 'gemini'."
    )


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """FastAPI dependency that builds an AuthService for the current request.

    Wires together a UserRepository backed by the request-scoped DB session
    and the application settings.

    Args:
        db: SQLAlchemy Session injected by FastAPI.

    Returns:
        A fully configured AuthService instance.
    """
    settings = get_settings()
    return AuthService(UserRepository(db), settings)


def get_file_upload_service(db: Session = Depends(get_db)) -> FileUploadService:
    """FastAPI dependency that builds a FileUploadService for the current request.

    Wires together a CSVRepository, S3FileStorageAdapter, and EventRepository
    backed by the request-scoped DB session and application settings.

    Args:
        db: SQLAlchemy Session injected by FastAPI.

    Returns:
        A fully configured FileUploadService instance.
    """
    settings = get_settings()
    storage_adapters = _build_storage_adapters(settings)
    return FileUploadService(
        csv_repo=CSVRepository(db),
        storage=storage_adapters.get("minio") or S3FileStorageAdapter(settings),
        storage_by_provider=storage_adapters,
        event_repo=EventRepository(db),
        settings=settings,
    )


def get_document_analysis_service(
    db: Session = Depends(get_db),
) -> DocumentAnalysisService:
    """FastAPI dependency that builds a DocumentAnalysisService for the current request.

    Wires together a GeminiDocumentAdapter, S3FileStorageAdapter,
    DocumentRepository, and EventRepository backed by the request-scoped
    DB session and application settings.

    Args:
        db: SQLAlchemy Session injected by FastAPI.

    Returns:
        A fully configured DocumentAnalysisService instance.
    """
    settings = get_settings()
    storage_adapters = _build_storage_adapters(settings)
    return DocumentAnalysisService(
        ai_port=_build_document_ai_adapter(settings),
        storage=storage_adapters.get("minio") or S3FileStorageAdapter(settings),
        storage_by_provider=storage_adapters,
        document_repo=DocumentRepository(db),
        event_repo=EventRepository(db),
        settings=settings,
    )


def get_event_service(db: Session = Depends(get_db)) -> EventService:
    """FastAPI dependency that builds an EventService for the current request.

    Wires together an EventRepository backed by the request-scoped DB session.

    Args:
        db: SQLAlchemy Session injected by FastAPI.

    Returns:
        A fully configured EventService instance.
    """
    return EventService(EventRepository(db))
