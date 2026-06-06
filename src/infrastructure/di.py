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
from src.infrastructure.ai.ollama_adapter import OllamaDocumentAdapter
from src.infrastructure.ai.openai_adapter import OpenAIDocumentAdapter
from src.infrastructure.db.session import get_db
from src.infrastructure.repositories.csv_repository import CSVRepository
from src.infrastructure.repositories.document_repository import DocumentRepository
from src.infrastructure.repositories.event_repository import EventRepository
from src.infrastructure.repositories.user_repository import UserRepository
from src.infrastructure.storage.s3_adapter import S3FileStorageAdapter


def _build_document_ai_adapter(settings):
    provider = settings.AI_PROVIDER.strip().lower()
    if provider == "openai":
        return OpenAIDocumentAdapter(settings)
    if provider == "gemini":
        return GeminiDocumentAdapter(settings)
    if provider == "ollama":
        return OllamaDocumentAdapter(settings)

    raise ValueError(
        f"Unsupported AI_PROVIDER '{settings.AI_PROVIDER}'. Use 'openai', 'gemini' or 'ollama'."
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
    return FileUploadService(
        csv_repo=CSVRepository(db),
        storage=S3FileStorageAdapter(settings),
        event_repo=EventRepository(db),
        settings=settings,
    )


def get_document_analysis_service(
    db: Session = Depends(get_db),
) -> DocumentAnalysisService:
    """FastAPI dependency that builds a DocumentAnalysisService for the current request.

    Wires together an OpenAIDocumentAdapter, S3FileStorageAdapter,
    DocumentRepository, and EventRepository backed by the request-scoped
    DB session and application settings.

    Args:
        db: SQLAlchemy Session injected by FastAPI.

    Returns:
        A fully configured DocumentAnalysisService instance.
    """
    settings = get_settings()
    return DocumentAnalysisService(
        ai_port=_build_document_ai_adapter(settings),
        storage=S3FileStorageAdapter(settings),
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
