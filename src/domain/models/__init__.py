"""Domain models package.

Re-exports all domain entities and value types for convenient single-import access.
The CSV ``ValidationError`` dataclass is exported as ``CSVValidationError`` to avoid
a name collision with the ``ValidationError`` domain exception in ``src.domain.exceptions``.
"""

from .csv_upload import CSVRow, CSVUpload, UploadResult
from .csv_upload import ValidationError as CSVValidationError
from .document import (
    AnalysisResult,
    Document,
    DocumentType,
    InformationData,
    InvoiceData,
    InvoiceProduct,
    Sentiment,
)
from .event import Event, EventType
from .user import User, UserRole

__all__ = [
    # User
    "User",
    "UserRole",
    # CSV
    "CSVUpload",
    "CSVRow",
    "CSVValidationError",
    "UploadResult",
    # Document
    "Document",
    "DocumentType",
    "Sentiment",
    "InvoiceProduct",
    "InvoiceData",
    "InformationData",
    "AnalysisResult",
    # Event
    "Event",
    "EventType",
]
