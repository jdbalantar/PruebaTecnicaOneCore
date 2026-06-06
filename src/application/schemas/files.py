"""Pydantic schemas for CSV file-upload endpoints."""

from pydantic import BaseModel


class ValidationErrorSchema(BaseModel):
    """A single validation failure found during CSV parsing."""

    row_number: int
    column: str
    error_type: str
    message: str


class UploadResultResponse(BaseModel):
    """Summary returned after a CSV upload and validation run."""

    upload_id: str
    filename: str
    s3_key: str
    storage_provider: str | None = None
    storage_bucket: str | None = None
    total_rows: int
    valid_rows: int
    error_rows: int
    status: str
    validations: list[ValidationErrorSchema]
