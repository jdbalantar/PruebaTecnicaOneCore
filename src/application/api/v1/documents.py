"""Documents router — AI classification and extraction endpoint."""

import dataclasses
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.application.dependencies import get_current_user_payload, get_user_id_from_payload
from src.application.schemas.documents import AnalysisResultResponse
from src.application.schemas.result import Result, ok
from src.domain.services.document_analysis_service import DocumentAnalysisService
from src.infrastructure.di import get_document_analysis_service

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}


@router.post("/analyze")
async def analyze_document(
    file: Annotated[UploadFile, File(...)],
    payload: Annotated[dict, Depends(get_current_user_payload)],
    service: Annotated[DocumentAnalysisService, Depends(get_document_analysis_service)],
) -> Result[AnalysisResultResponse]:
    """Uploads a PDF/JPG/PNG document, classifies it using AI, and extracts structured data.

    Requires: valid JWT (any role).

    Args:
        file: The document file to analyse (PDF, JPEG, or PNG).
        payload: Decoded JWT payload — injected by ``get_current_user_payload``.
        service: DocumentAnalysisService injected by FastAPI.

    Returns:
        AnalysisResultResponse with document type, confidence score, and extracted fields.

    Raises:
        HTTPException: 415 if the content type is not PDF, JPEG, or PNG.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    file_bytes = await file.read()
    user_id = get_user_id_from_payload(payload)

    result = service.analyze(
        file_bytes=file_bytes,
        filename=file.filename,
        content_type=file.content_type,
        user_id=user_id,
    )

    extracted = None
    if result.extracted_data is not None:
        extracted = dataclasses.asdict(result.extracted_data)

    return ok(
        AnalysisResultResponse(
            document_id=str(result.document_id),
            doc_type=result.doc_type.value,
            confidence=result.confidence,
            extracted_data=extracted,
            ai_model=result.ai_model,
            fallback_used=result.fallback_used,
            fallback_reason=result.fallback_reason,
        )
    )
