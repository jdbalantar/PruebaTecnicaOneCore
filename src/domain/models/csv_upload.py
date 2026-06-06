"""Domain entities for CSV upload processing."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class ValidationError:
    """A single per-row validation failure discovered during CSV parsing.

    Attributes:
        row_number: 1-indexed row position in the source file.
        column: Name of the column that failed validation (empty for row-level errors).
        error_type: Machine-readable category: ``"empty"``, ``"type_mismatch"``, or ``"duplicate"``.
        message: Human-readable description of the failure.
    """

    row_number: int
    column: str
    error_type: str  # "empty", "type_mismatch", "duplicate"
    message: str


@dataclass
class CSVRow:
    """A single parsed row from a CSV upload.

    Attributes:
        id: Auto-assigned database surrogate key; ``None`` before persistence.
        upload_id: FK to the parent CSVUpload.
        row_number: 1-indexed position in the source file.
        row_data: Raw column-name → value mapping from the CSV.
        validation_errors: All validation failures found for this row.
    """

    id: int | None
    upload_id: UUID
    row_number: int
    row_data: dict
    validation_errors: list[ValidationError] = field(default_factory=list)


@dataclass
class CSVUpload:
    """Metadata and content for a complete CSV upload operation.

    Attributes:
        id: Unique identifier for this upload (UUID v4).
        user_id: ID of the authenticated user who initiated the upload.
        filename: Original filename provided by the client.
        s3_key: Object key under which the raw file is stored in S3.
        s3_bucket: Name of the S3 bucket holding the file.
        validation_mode: ``"strict"`` (reject on any error) or ``"lenient"`` (collect errors).
        allow_duplicates: Whether duplicate rows are accepted.
        status: Processing state: ``"pending"``, ``"completed"``, or ``"failed"``.
        rows: Parsed and validated row objects.
        created_at: UTC timestamp of upload creation.
        updated_at: UTC timestamp of last status change.
    """

    id: UUID
    user_id: UUID
    filename: str
    s3_key: str
    s3_bucket: str
    validation_mode: str  # "strict" | "lenient"
    allow_duplicates: bool
    status: str  # "pending" | "completed" | "failed"
    rows: list[CSVRow] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UploadResult:
    """Summary returned to the caller after a CSV upload + validation run.

    Attributes:
        upload_id: UUID of the persisted CSVUpload record.
        filename: Original filename.
        s3_key: S3 object key of the uploaded file.
        total_rows: Total number of data rows in the file.
        valid_rows: Number of rows that passed all validation checks.
        error_rows: Number of rows that contained at least one error.
        validations: Flat list of all validation errors across all rows.
        status: Final processing status: ``"completed"`` or ``"failed"``.
    """

    upload_id: UUID
    filename: str
    s3_key: str
    total_rows: int
    valid_rows: int
    error_rows: int
    validations: list[ValidationError]
    status: str
    storage_provider: str | None = None
    storage_bucket: str | None = None
