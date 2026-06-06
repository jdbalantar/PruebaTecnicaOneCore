"""Shared pytest fixtures for the PruebaTecnica test suite."""

import pytest
from unittest.mock import MagicMock, create_autospec
from uuid import uuid4
from datetime import datetime, timezone

from src.domain.models.user import User, UserRole
from src.domain.models.event import Event, EventType
from src.domain.models.csv_upload import CSVUpload, CSVRow, UploadResult
from src.domain.models.document import Document, DocumentType, Sentiment, InvoiceData, InformationData
from src.domain.ports.user_repository import IUserRepository
from src.domain.ports.file_storage import IFileStoragePort
from src.domain.ports.document_ai import IDocumentAIPort
from src.domain.ports.csv_repository import ICSVRepository
from src.domain.ports.event_repository import IEventRepository, EventFilters, EventPage
from src.domain.ports.document_repository import IDocumentRepository


@pytest.fixture
def mock_settings():
    """Application settings mock with HS256 JWT config and test limits."""
    settings = MagicMock()
    settings.JWT_ALGORITHM = "HS256"
    settings.JWT_PRIVATE_KEY = "test-secret-key"
    settings.JWT_PUBLIC_KEY = "test-secret-key"
    settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15
    settings.S3_BUCKET_CSV = "test-csv-bucket"
    settings.S3_BUCKET_DOCS = "test-docs-bucket"
    settings.CSV_MAX_FILE_SIZE_MB = 10
    settings.CSV_MAX_ROWS = 50000
    settings.OPENAI_API_KEY = "test-key"
    settings.OPENAI_MODEL_CLASSIFY = "gpt-4o-mini"
    settings.OPENAI_MODEL_EXTRACT = "gpt-4o"
    return settings


@pytest.fixture
def sample_user():
    """A standard active UPLOADER user entity."""
    return User(
        id=uuid4(),
        username="testuser",
        password_hash="$2b$12$placeholder",  # bcrypt hash placeholder
        rol=UserRole.UPLOADER,
        created_at=datetime.now(timezone.utc),
        is_active=True,
    )


@pytest.fixture
def mock_user_repo():
    """Type-safe autospec mock of IUserRepository."""
    return create_autospec(IUserRepository)


@pytest.fixture
def mock_storage():
    """Type-safe autospec mock of IFileStoragePort, pre-configured to return a key."""
    storage = create_autospec(IFileStoragePort)
    storage.upload_file.return_value = "test/key.csv"
    return storage


@pytest.fixture
def mock_ai_port():
    """Type-safe autospec mock of IDocumentAIPort."""
    return create_autospec(IDocumentAIPort)


@pytest.fixture
def mock_csv_repo():
    """Type-safe autospec mock of ICSVRepository; save_upload echoes the input."""
    repo = create_autospec(ICSVRepository)
    repo.save_upload.side_effect = lambda u: u
    return repo


@pytest.fixture
def mock_event_repo():
    """Type-safe autospec mock of IEventRepository; log_event echoes the input."""
    repo = create_autospec(IEventRepository)
    repo.log_event.side_effect = lambda e: e
    return repo


@pytest.fixture
def mock_document_repo():
    """Type-safe autospec mock of IDocumentRepository; save echoes the input."""
    repo = create_autospec(IDocumentRepository)
    repo.save.side_effect = lambda d: d
    return repo
