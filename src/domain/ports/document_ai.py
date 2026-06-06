"""Port: IDocumentAIPort — abstract AI classification and extraction interface."""

from abc import ABC, abstractmethod

from ..models.document import DocumentType, InformationData, InvoiceData


class IDocumentAIPort(ABC):
    """Abstract port for AI-powered document analysis.

    Implementations wrap an external AI provider and are
    injected at application startup.
    """

    @abstractmethod
    def classify_document(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[DocumentType, float]:
        """Classify a document and return its type with a confidence score.

        Args:
            file_bytes: Raw binary content of the document.
            filename: Original filename (used as context for the model).
            content_type: MIME type (e.g. ``"application/pdf"``).

        Returns:
            A tuple of ``(DocumentType, confidence)`` where confidence is 0–1.

        Raises:
            AIServiceError: If the AI provider call fails after retries.
        """
        ...

    @abstractmethod
    def extract_invoice_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InvoiceData:
        """Extract structured invoice data from a document classified as INVOICE.

        Args:
            file_bytes: Raw binary content of the document.
            filename: Original filename.
            content_type: MIME type.

        Returns:
            Fully populated :class:`InvoiceData` instance.

        Raises:
            AIServiceError: If extraction fails after retries.
        """
        ...

    @abstractmethod
    def extract_info_data(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> InformationData:
        """Extract structured information data from a document classified as INFORMATION.

        Args:
            file_bytes: Raw binary content of the document.
            filename: Original filename.
            content_type: MIME type.

        Returns:
            Fully populated :class:`InformationData` instance.

        Raises:
            AIServiceError: If extraction fails after retries.
        """
        ...
