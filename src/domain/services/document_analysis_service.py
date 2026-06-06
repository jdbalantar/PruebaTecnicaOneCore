"""Domain service: DocumentAnalysisService — document upload, AI classification, and extraction."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from ..exceptions import AIServiceError, StorageError, ValidationError
from ..models.document import AnalysisResult, Document, DocumentType
from ..models.event import Event, EventType
from ..ports.document_ai import IDocumentAIPort
from ..ports.document_repository import IDocumentRepository
from ..ports.event_repository import IEventRepository
from ..ports.file_storage import IFileStoragePort

_SUPPORTED_CONTENT_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "application/pdf"}
)


class DocumentAnalysisService:
    """Manages document upload, AI classification, data extraction, and persistence.

    Orchestrates the full document analysis pipeline: content-type validation,
    S3 upload, AI classification, structured data extraction, DB persistence,
    and audit logging.

    Args:
        ai_port: Port for AI-powered document classification and extraction.
        storage: File-storage port for uploading raw bytes to S3.
        document_repo: Repository for persisting Document entities.
        event_repo: Event repository for writing audit-log entries.
        settings: Application settings (provides bucket names and AI model names).
    """

    def __init__(
        self,
        ai_port: IDocumentAIPort,
        storage: IFileStoragePort,
        document_repo: IDocumentRepository,
        event_repo: IEventRepository,
        settings,
        storage_by_provider: dict[str, IFileStoragePort] | None = None,
    ) -> None:
        self._ai_port = ai_port
        self._storage = storage
        self._storage_by_provider = {"minio": storage}
        if storage_by_provider:
            self._storage_by_provider.update(
                {k.strip().lower(): v for k, v in storage_by_provider.items()}
            )
        self._document_repo = document_repo
        self._event_repo = event_repo
        self._settings = settings

    def _active_models(self) -> tuple[str, str]:
        return self._settings.GEMINI_MODEL_CLASSIFY, self._settings.GEMINI_MODEL_EXTRACT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: UUID | None,
        storage_provider: str | None = None,
    ) -> AnalysisResult:
        """Upload a document to S3, classify it with AI, and extract structured data.

        Processing steps:
        1. Validate that ``content_type`` is one of: ``image/jpeg``, ``image/png``,
           ``application/pdf``.
        2. Upload the raw file to S3 at
           ``documents/{user_id or 'anonymous'}/{timestamp}_{filename}``.
        3. Call the AI port to classify the document and obtain a confidence score.
        4. If the type is INVOICE, extract invoice line-item data.
           If the type is INFORMATION, extract description/summary/sentiment data.
           If UNKNOWN, skip extraction.
        5. Persist the Document entity to the database.
        6. Log ``DOC_UPLOAD``, ``AI_CLASSIFICATION``, and (when applicable)
           ``AI_EXTRACTION`` audit events.

        Args:
            file_bytes: Raw binary file content (PDF / JPEG / PNG).
            filename: Original client-provided filename.
            content_type: MIME type of the document.
            user_id: Optional UUID of the uploading user; ``None`` for anonymous uploads.

        Returns:
            :class:`AnalysisResult` containing the detected document type,
            confidence score, extracted structured data, and AI model name.

        Raises:
            ValidationError: If ``content_type`` is not supported.
            StorageError: If the S3 upload fails.
            AIServiceError: If AI classification or extraction fails after retries.
        """
        # 1. Validate content type
        if content_type not in _SUPPORTED_CONTENT_TYPES:
            raise ValidationError(
                f"Unsupported content type '{content_type}'. "
                f"Allowed types: {', '.join(sorted(_SUPPORTED_CONTENT_TYPES))}"
            )

        # 2. Upload to S3
        selected_provider, selected_storage, bucket = self._resolve_storage_for_docs(
            storage_provider
        )

        owner_segment = str(user_id) if user_id is not None else "anonymous"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"documents/{owner_segment}/{timestamp}_{filename}"

        try:
            selected_storage.upload_file(
                file_bytes=file_bytes,
                key=s3_key,
                bucket=bucket,
                content_type=content_type,
                metadata={
                    "user_id": owner_segment,
                    "filename": filename,
                    "content_type": content_type,
                },
            )
        except Exception as exc:
            raise StorageError(f"Failed to upload document to S3: {exc}") from exc

        self._log_event(
            event_type=EventType.DOC_UPLOAD,
            description=f"Document '{filename}' uploaded to S3",
            metadata={
                "filename": filename,
                "content_type": content_type,
                "s3_key": s3_key,
                "s3_bucket": bucket,
                "storage_provider": selected_provider,
            },
            user_id=user_id,
        )

        # 3. Classify with AI
        fallback_reason: str | None = None
        try:
            doc_type, confidence = self._ai_port.classify_document(
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
            )
        except Exception as exc:
            if self._is_ai_quota_or_rate_limit_error(exc):
                # Graceful degradation for local/dev environments without AI quota.
                doc_type = DocumentType.UNKNOWN
                confidence = 0.0
                fallback_reason = str(exc)
            else:
                raise AIServiceError(f"Document classification failed: {exc}") from exc

        classify_model, extract_model = self._active_models()
        ai_model = classify_model if fallback_reason is None else "fallback:no-ai"
        self._log_event(
            event_type=EventType.AI_CLASSIFICATION,
            description=(
                f"Document '{filename}' classified as {doc_type.value} "
                f"(confidence={confidence:.2f})"
            ),
            metadata={
                "filename": filename,
                "doc_type": doc_type.value,
                "confidence": confidence,
                "ai_model": ai_model,
                "fallback_reason": fallback_reason,
            },
            user_id=user_id,
        )

        # 4. Extract structured data based on classification
        extracted_data = None
        if doc_type == DocumentType.INVOICE:
            try:
                extracted_data = self._ai_port.extract_invoice_data(
                    file_bytes=file_bytes,
                    filename=filename,
                    content_type=content_type,
                )
            except Exception as exc:
                raise AIServiceError(f"Invoice data extraction failed: {exc}") from exc
            extraction_model = extract_model
            ai_model = extraction_model
            self._log_event(
                event_type=EventType.AI_EXTRACTION,
                description=f"Invoice data extracted from '{filename}'",
                metadata={
                    "filename": filename,
                    "doc_type": doc_type.value,
                    "ai_model": extraction_model,
                },
                user_id=user_id,
            )
        elif doc_type == DocumentType.INFORMATION:
            try:
                extracted_data = self._ai_port.extract_info_data(
                    file_bytes=file_bytes,
                    filename=filename,
                    content_type=content_type,
                )
            except Exception as exc:
                raise AIServiceError(f"Information data extraction failed: {exc}") from exc
            extraction_model = extract_model
            ai_model = extraction_model
            self._log_event(
                event_type=EventType.AI_EXTRACTION,
                description=f"Information data extracted from '{filename}'",
                metadata={
                    "filename": filename,
                    "doc_type": doc_type.value,
                    "ai_model": extraction_model,
                },
                user_id=user_id,
            )

        # 5. Persist Document entity
        persisted_doc_type = (
            DocumentType.INFORMATION
            if doc_type == DocumentType.UNKNOWN
            else doc_type
        )
        document = Document(
            id=uuid4(),
            user_id=user_id,
            filename=filename,
            s3_key=s3_key,
            s3_bucket=bucket,
            doc_type=persisted_doc_type,
            extracted_data=extracted_data,
            ai_model=ai_model,
            confidence=confidence,
            created_at=datetime.now(timezone.utc),
        )
        saved_document = self._document_repo.save(document)

        # 6. Return analysis result
        return AnalysisResult(
            document_id=saved_document.id,
            doc_type=doc_type,
            confidence=confidence,
            extracted_data=extracted_data,
            ai_model=ai_model,
            fallback_used=fallback_reason is not None,
            fallback_reason=fallback_reason,
            storage_provider=selected_provider,
            storage_bucket=bucket,
        )

    def _resolve_storage_for_docs(
        self,
        storage_provider: str | None,
    ) -> tuple[str, IFileStoragePort, str]:
        provider = (storage_provider or self._settings.STORAGE_DEFAULT_PROVIDER or "minio").strip().lower()
        selected_storage = self._storage_by_provider.get(provider)
        if selected_storage is None:
            raise ValidationError(
                f"Unsupported storage provider '{provider}'. Allowed providers: minio, localstack"
            )

        if provider == "localstack":
            bucket = self._settings.LOCALSTACK_BUCKET_DOCS
        else:
            bucket = self._settings.MINIO_BUCKET_DOCS or self._settings.S3_BUCKET_DOCS

        return provider, selected_storage, bucket

    @staticmethod
    def _is_ai_quota_or_rate_limit_error(exc: Exception) -> bool:
        """Return True when AI failures are quota/rate-limit related and recoverable."""
        text = str(exc).lower()
        markers = {
            "insufficient_quota",
            "rate limit",
            "rate_limit",
            "you exceeded your current quota",
            "error code: 429",
        }
        return any(marker in text for marker in markers)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _log_event(
        self,
        event_type: EventType,
        description: str,
        metadata: dict,
        user_id: UUID | None,
    ) -> None:
        """Create and persist a single audit-log event.

        Args:
            event_type: Category of the event.
            description: Human-readable summary.
            metadata: Structured key-value payload.
            user_id: UUID of the acting user, or ``None`` for anonymous.
        """
        event = Event(
            id=uuid4(),
            event_type=event_type,
            description=description,
            metadata=metadata,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )
        self._event_repo.log_event(event)
