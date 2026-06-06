"""Unit tests for DocumentAnalysisService — document upload, AI classification, extraction."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from src.domain.exceptions import AIServiceError, ValidationError
from src.domain.models.document import (
    DocumentType,
    InformationData,
    InvoiceData,
    InvoiceProduct,
    Sentiment,
)
from src.domain.models.event import EventType
from src.domain.services.document_analysis_service import DocumentAnalysisService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FILE_BYTES = b"%PDF-1.4 fake pdf content"
_FILENAME = "invoice.pdf"
_USER_ID = uuid4()

_INVOICE_DATA = InvoiceData(
    client_name="ACME Corp",
    client_address="123 Main St",
    supplier_name="Vendor SA",
    supplier_address="456 Oak Ave",
    invoice_number="INV-001",
    date="2024-01-15",
    products=[InvoiceProduct(quantity=1, name="Widget", unit_price=100.0, total=100.0)],
    total=100.0,
)

_INFO_DATA = InformationData(
    description="A regulatory document about compliance requirements.",
    summary="Compliance overview.",
    sentiment=Sentiment.NEUTRAL,
)


def _make_service(
    mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
) -> DocumentAnalysisService:
    """Instantiate DocumentAnalysisService with injected mocks."""
    return DocumentAnalysisService(
        ai_port=mock_ai_port,
        storage=mock_storage,
        document_repo=mock_document_repo,
        event_repo=mock_event_repo,
        settings=mock_settings,
    )


def _configure_ai(mock_ai_port, doc_type: DocumentType, confidence: float = 0.95):
    """Configure the AI port mock to return the given document type."""
    mock_ai_port.classify_document.return_value = (doc_type, confidence)
    mock_ai_port.extract_invoice_data.return_value = _INVOICE_DATA
    mock_ai_port.extract_info_data.return_value = _INFO_DATA


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDocumentAnalysis:
    """Tests for DocumentAnalysisService.analyze."""

    @pytest.mark.parametrize(
        "content_type",
        ["image/jpeg", "image/png", "application/pdf"],
    )
    def test_supported_content_types_call_classify(
        self,
        content_type,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """All supported MIME types must reach the AI classify_document call."""
        _configure_ai(mock_ai_port, DocumentType.UNKNOWN)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        service.analyze(b"data", "file", content_type, _USER_ID)

        mock_ai_port.classify_document.assert_called_once_with(
            file_bytes=b"data",
            filename="file",
            content_type=content_type,
        )

    def test_analyze_jpeg_calls_classify(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """image/jpeg must be accepted and forwarded to the AI port."""
        _configure_ai(mock_ai_port, DocumentType.UNKNOWN)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        result = service.analyze(b"jpeg-data", "photo.jpg", "image/jpeg", _USER_ID)

        assert result.doc_type == DocumentType.UNKNOWN
        mock_ai_port.classify_document.assert_called_once()

    def test_analyze_pdf_calls_classify(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """application/pdf must be accepted and forwarded to the AI port."""
        _configure_ai(mock_ai_port, DocumentType.INVOICE)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        result = service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        assert result.doc_type == DocumentType.INVOICE
        mock_ai_port.classify_document.assert_called_once()

    def test_analyze_png_calls_classify(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """image/png must be accepted and forwarded to the AI port."""
        _configure_ai(mock_ai_port, DocumentType.INFORMATION)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        result = service.analyze(b"png-data", "scan.png", "image/png", _USER_ID)

        assert result.doc_type == DocumentType.INFORMATION

    def test_unsupported_content_type_raises_validation_error(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """An unsupported MIME type must raise ValidationError before any AI call."""
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        with pytest.raises(ValidationError):
            service.analyze(b"data", "file.docx", "application/msword", _USER_ID)

        mock_ai_port.classify_document.assert_not_called()

    def test_invoice_type_triggers_invoice_extraction(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """INVOICE classification must trigger extract_invoice_data, not extract_info_data."""
        _configure_ai(mock_ai_port, DocumentType.INVOICE)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        result = service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        mock_ai_port.extract_invoice_data.assert_called_once()
        mock_ai_port.extract_info_data.assert_not_called()
        assert result.extracted_data == _INVOICE_DATA

    def test_information_type_triggers_info_extraction(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """INFORMATION classification must trigger extract_info_data, not extract_invoice_data."""
        _configure_ai(mock_ai_port, DocumentType.INFORMATION)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        result = service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        mock_ai_port.extract_info_data.assert_called_once()
        mock_ai_port.extract_invoice_data.assert_not_called()
        assert result.extracted_data == _INFO_DATA

    def test_unknown_type_returns_no_extraction(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """UNKNOWN classification must skip both extraction methods."""
        _configure_ai(mock_ai_port, DocumentType.UNKNOWN)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        result = service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        mock_ai_port.extract_invoice_data.assert_not_called()
        mock_ai_port.extract_info_data.assert_not_called()
        assert result.extracted_data is None

    def test_document_saved_to_db(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """The document repository's save must be called exactly once."""
        _configure_ai(mock_ai_port, DocumentType.UNKNOWN)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        mock_document_repo.save.assert_called_once()
        saved_doc = mock_document_repo.save.call_args.args[0]
        assert saved_doc.filename == _FILENAME
        assert saved_doc.user_id == _USER_ID

    def test_event_logged_after_analysis(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """At least DOC_UPLOAD and AI_CLASSIFICATION events must be logged."""
        _configure_ai(mock_ai_port, DocumentType.UNKNOWN)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        assert mock_event_repo.log_event.call_count >= 2
        logged_types = {c.args[0].event_type for c in mock_event_repo.log_event.call_args_list}
        assert EventType.DOC_UPLOAD in logged_types
        assert EventType.AI_CLASSIFICATION in logged_types

    def test_extraction_event_logged_for_invoice(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """An AI_EXTRACTION event must be logged when doc_type is INVOICE."""
        _configure_ai(mock_ai_port, DocumentType.INVOICE)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        logged_types = {c.args[0].event_type for c in mock_event_repo.log_event.call_args_list}
        assert EventType.AI_EXTRACTION in logged_types

    def test_s3_upload_called_with_correct_key(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """S3 upload must target the docs bucket and embed the user UUID in the key."""
        _configure_ai(mock_ai_port, DocumentType.UNKNOWN)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        call_kwargs = mock_storage.upload_file.call_args.kwargs
        assert call_kwargs["bucket"] == mock_settings.S3_BUCKET_DOCS
        assert str(_USER_ID) in call_kwargs["key"]
        assert _FILENAME in call_kwargs["key"]

    def test_ai_service_error_propagates(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """An exception from classify_document must be wrapped and re-raised as AIServiceError."""
        mock_ai_port.classify_document.side_effect = RuntimeError("AI timeout")
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        with pytest.raises(AIServiceError, match="classification"):
            service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

    @pytest.mark.parametrize(
        "doc_type,expected_method",
        [
            (DocumentType.INVOICE, "extract_invoice_data"),
            (DocumentType.INFORMATION, "extract_info_data"),
        ],
    )
    def test_extraction_method_matches_doc_type(
        self,
        doc_type,
        expected_method,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """The correct extraction method must be called for each classifiable doc_type."""
        _configure_ai(mock_ai_port, doc_type)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", _USER_ID)

        getattr(mock_ai_port, expected_method).assert_called_once()

    def test_anonymous_upload_uses_anonymous_segment_in_key(
        self,
        mock_ai_port,
        mock_storage,
        mock_document_repo,
        mock_event_repo,
        mock_settings,
    ):
        """When user_id is None the S3 key must contain 'anonymous'."""
        _configure_ai(mock_ai_port, DocumentType.UNKNOWN)
        service = _make_service(
            mock_ai_port, mock_storage, mock_document_repo, mock_event_repo, mock_settings
        )

        service.analyze(_FILE_BYTES, _FILENAME, "application/pdf", user_id=None)

        call_kwargs = mock_storage.upload_file.call_args.kwargs
        assert "anonymous" in call_kwargs["key"]
