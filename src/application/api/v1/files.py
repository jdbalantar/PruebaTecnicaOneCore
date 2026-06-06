"""Files router — CSV upload and validation endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.application.dependencies import require_role
from src.application.schemas.files import UploadResultResponse, ValidationErrorSchema
from src.application.schemas.result import Result, ok
from src.domain.services.file_upload_service import FileUploadService
from src.infrastructure.di import get_file_upload_service

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/upload",
    responses={400: {"description": "Only CSV files are accepted"}},
)
async def upload_csv(
    file: Annotated[UploadFile, File(...)],
    payload: Annotated[dict, Depends(require_role("admin", "uploader"))],
    service: Annotated[FileUploadService, Depends(get_file_upload_service)],
    validation_mode: Annotated[str, Form()] = "lenient",
    allow_duplicates: Annotated[bool, Form()] = False,
) -> Result[UploadResultResponse]:
    """Uploads a CSV file, validates its content, and stores it to S3 and SQL Server.

    Requires role: ``admin`` or ``uploader``.

    Args:
        file: The CSV file to upload (``multipart/form-data``).
        validation_mode: ``"strict"`` rejects on first error;
            ``"lenient"`` (default) collects all errors before responding.
        allow_duplicates: Whether duplicate rows are permitted (default ``False``).
        payload: Decoded JWT payload — injected by the ``require_role`` guard.
        service: FileUploadService injected by FastAPI.

    Returns:
        UploadResultResponse with validation summary and S3 reference.

    Raises:
        HTTPException: 400 if the uploaded file is not a CSV.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    file_bytes = await file.read()
    user_id = UUID(payload["sub"])

    result = service.upload_and_validate(
        file_bytes=file_bytes,
        filename=file.filename,
        validation_mode=validation_mode,
        allow_duplicates=allow_duplicates,
        user_id=user_id,
    )

    return ok(
        UploadResultResponse(
            upload_id=str(result.upload_id),
            filename=result.filename,
            s3_key=result.s3_key,
            total_rows=result.total_rows,
            valid_rows=result.valid_rows,
            error_rows=result.error_rows,
            status=result.status,
            validations=[
                ValidationErrorSchema(
                    row_number=v.row_number,
                    column=v.column,
                    error_type=v.error_type,
                    message=v.message,
                )
                for v in result.validations
            ],
        )
    )
