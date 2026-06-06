"""Domain entities for document upload and AI analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class DocumentType(str, Enum):
    """AI-assigned document classification."""

    INVOICE = "invoice"
    INFORMATION = "information"
    UNKNOWN = "unknown"


class Sentiment(str, Enum):
    """Sentiment detected in an informational document."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class InvoiceProduct:
    """A single line item within an invoice.

    Attributes:
        quantity: Number of units purchased.
        name: Product or service name.
        unit_price: Price per unit (before tax).
        total: Line total (quantity × unit_price).
    """

    quantity: float
    name: str
    unit_price: float
    total: float


@dataclass
class InvoiceData:
    """Structured data extracted from an invoice document.

    Attributes:
        client_name: Name of the buyer.
        client_address: Billing address of the buyer.
        supplier_name: Name of the issuing vendor.
        supplier_address: Address of the issuing vendor.
        invoice_number: Vendor-assigned invoice identifier.
        date: Invoice date as a string (ISO-8601 preferred).
        products: List of line items.
        total: Grand total of the invoice.
    """

    client_name: str
    client_address: str
    supplier_name: str
    supplier_address: str
    invoice_number: str
    date: str
    products: list[InvoiceProduct]
    total: float


@dataclass
class InformationData:
    """Structured data extracted from an informational document.

    Attributes:
        description: Full description of the document content.
        summary: Short AI-generated summary.
        sentiment: Detected emotional tone of the document.
    """

    description: str
    summary: str
    sentiment: Sentiment


@dataclass
class Document:
    """Core document entity representing a stored and analysed file.

    Attributes:
        id: Unique identifier (UUID v4).
        user_id: ID of the user who uploaded the file; ``None`` for anonymous uploads.
        filename: Original client-provided filename.
        s3_key: Object key in the documents S3 bucket.
        s3_bucket: Name of the S3 bucket.
        doc_type: AI-assigned document classification.
        extracted_data: Structured data extracted by the AI; typed by ``doc_type``.
        ai_model: Name of the AI model used for analysis.
        confidence: Classification confidence score (0–1).
        created_at: UTC timestamp of document creation.
    """

    id: UUID
    user_id: UUID | None
    filename: str
    s3_key: str
    s3_bucket: str
    doc_type: DocumentType
    extracted_data: InvoiceData | InformationData | None
    ai_model: str | None
    confidence: float | None
    created_at: datetime


@dataclass
class AnalysisResult:
    """Result returned to the caller after document analysis completes.

    Attributes:
        document_id: UUID of the persisted Document record.
        doc_type: Detected document type.
        confidence: Classification confidence score (0–1).
        extracted_data: Structured extraction output; typed by ``doc_type``.
        ai_model: Name of the AI model used.
    """

    document_id: UUID
    doc_type: DocumentType
    confidence: float
    extracted_data: InvoiceData | InformationData | None
    ai_model: str
    fallback_used: bool = False
    fallback_reason: str | None = None
